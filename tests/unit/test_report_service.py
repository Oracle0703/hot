import os
from pathlib import Path

import pytest
from sqlalchemy import select
from zipfile import ZipFile

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.item import CollectedItem
from app.models.job import CollectionJob
from app.models.job_log import JobLog
from app.models.report import Report
from app.models.source import Source
from app.services.job_service import JobService
from app.services.report_service import ReportService
from app.workers.runner import JobRunner


TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
def setup_database(tmp_path: Path, name: str):
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    os.environ["REPORTS_ROOT"] = str(tmp_path / "reports")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def create_source(session, name: str, entry_url: str) -> Source:
    source = Source(
        name=name,
        site_name=name,
        entry_url=entry_url,
        fetch_mode="http",
        parser_type="generic_css",
        list_selector=".topic",
        title_selector=".topic-link",
        link_selector=".topic-link",
        meta_selector=".topic-time",
        include_keywords=[],
        exclude_keywords=[],
        max_items=10,
        enabled=True,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def test_runner_reuses_global_report_and_marks_item_status_across_jobs(tmp_path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'report-runner.db').as_posix()}"
    os.environ["REPORTS_ROOT"] = str(tmp_path / "reports")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory()

    with session_factory() as session:
        source = Source(
            name="本地来源",
            site_name="Local",
            entry_url="https://example.com/source",
            fetch_mode="http",
            parser_type="generic_css",
            list_selector=".topic",
            title_selector=".topic-link",
            link_selector=".topic-link",
            meta_selector=".topic-time",
            include_keywords=["新游"],
            exclude_keywords=[],
            max_items=10,
            enabled=True,
        )
        session.add(source)
        session.commit()
        source_id = source.id
        JobService(session).create_manual_job()
        JobService(session).create_manual_job()

    run_payloads = [
        {
            source_id: {
                "item_count": 2,
                "items": [
                    {
                        "title": "首次命中帖子",
                        "url": "https://example.com/post-1",
                        "published_at": "2026-03-24 08:00",
                    },
                    {
                        "title": "次轮未命中帖子",
                        "url": "https://example.com/post-2",
                        "published_at": "2026-03-24 09:00",
                    },
                ],
            }
        },
        {
            source_id: {
                "item_count": 1,
                "items": [
                    {
                        "title": "首次命中帖子",
                        "url": "https://example.com/post-1",
                        "published_at": "2026-03-24 08:00",
                    }
                ],
            }
        },
    ]

    def fake_source_executor(source: Source) -> dict[str, object]:
        payload = run_payloads[0 if fake_source_executor.call_count == 0 else 1]
        fake_source_executor.call_count += 1
        return payload[source.id]

    fake_source_executor.call_count = 0

    runner = JobRunner(session_factory=session_factory, source_executor=fake_source_executor)
    first_run_job_id = runner.run_once()

    with session_factory() as session:
        first_report = session.scalar(select(Report))
        first_job_row = session.get(CollectionJob, first_run_job_id)
        assert first_job_row is not None
        assert first_job_row.status == "success"
        assert first_report is not None
        assert Path(first_report.markdown_path).exists()
        assert Path(first_report.docx_path).exists()
        assert first_report.markdown_path.endswith("global\\hot-report.md")
        first_markdown = Path(first_report.markdown_path).read_text(encoding="utf-8")
        assert "### 来源: 本地来源" in first_markdown
        assert "[NEW] [首次命中帖子](https://example.com/post-1)" in first_markdown
        assert "[NEW] [次轮未命中帖子](https://example.com/post-2)" in first_markdown
        assert session.scalars(select(Report)).all() == [first_report]

    second_run_job_id = runner.run_once()

    with session_factory() as session:
        reports = session.scalars(select(Report)).all()
        second_report = reports[0]
        second_job_row = session.get(CollectionJob, second_run_job_id)
        assert second_job_row is not None
        assert second_job_row.status == "success"
        assert len(reports) == 1
        assert second_report.id == first_report.id
        assert second_report.job_id == second_run_job_id
        second_markdown = Path(second_report.markdown_path).read_text(encoding="utf-8")
        assert "[NEW] [首次命中帖子](https://example.com/post-1)" not in second_markdown
        assert "- [首次命中帖子](https://example.com/post-1) - 2026-03-24 08:00" in second_markdown
        assert "[本次未抓到] [次轮未命中帖子](https://example.com/post-2)" in second_markdown


def test_report_service_reuses_same_item_for_missing_url_with_title_and_published_at_hash(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "report-service-no-url.db")

    with session_factory() as session:
        source = create_source(session, "无链接来源", "https://example.com/source-a")
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        service = ReportService(session)

        service.generate_for_job(
            first_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "无链接帖子",
                            "published_at": "2026-03-24 08:00",
                            "excerpt": "first pass",
                        }
                    ],
                }
            ],
        )
        service.generate_for_job(
            second_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "无链接帖子",
                            "published_at": "2026-03-24 08:00",
                            "excerpt": "second pass",
                            "heat_score": "99",
                        }
                    ],
                }
            ],
        )

        items = list(session.scalars(select(CollectedItem)).all())

        assert len(items) == 1
        assert items[0].url == ""
        assert items[0].first_seen_job_id == first_job.id
        assert items[0].last_seen_job_id == second_job.id
        assert items[0].excerpt == "second pass"
        assert items[0].heat_score == "99"


def test_report_service_keeps_same_url_from_different_sources_as_separate_items(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "report-service-source-isolation.db")

    with session_factory() as session:
        first_source = create_source(session, "来源A", "https://example.com/source-a")
        second_source = create_source(session, "来源B", "https://example.com/source-b")
        job = JobService(session).create_manual_job()

        ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": first_source.id,
                    "source_name": first_source.name,
                    "items": [
                        {
                            "title": "相同链接帖子",
                            "url": "https://example.com/shared-post",
                            "published_at": "2026-03-24 08:00",
                        }
                    ],
                },
                {
                    "source_id": second_source.id,
                    "source_name": second_source.name,
                    "items": [
                        {
                            "title": "相同链接帖子",
                            "url": "https://example.com/shared-post",
                            "published_at": "2026-03-24 08:00",
                        }
                    ],
                },
            ],
        )

        items = list(session.scalars(select(CollectedItem).order_by(CollectedItem.source_id.asc())).all())

        assert len(items) == 2
        assert {item.source_id for item in items} == {first_source.id, second_source.id}
        assert all(item.url == "https://example.com/shared-post" for item in items)


def test_report_service_updates_existing_item_instead_of_inserting_duplicate_for_repeat_fetch(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "report-service-repeat-fetch.db")

    with session_factory() as session:
        source = create_source(session, "重复来源", "https://example.com/source-repeat")
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        service = ReportService(session)

        service.generate_for_job(
            first_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "重复帖子",
                            "url": "https://example.com/repeat-post",
                            "published_at": "2026-03-24 08:00",
                            "excerpt": "first snapshot",
                        }
                    ],
                }
            ],
        )
        service.generate_for_job(
            second_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "重复帖子-更新标题",
                            "url": "https://example.com/repeat-post",
                            "published_at": "2026-03-24 08:00",
                            "excerpt": "second snapshot",
                        }
                    ],
                }
            ],
        )

        items = list(session.scalars(select(CollectedItem)).all())

        assert len(items) == 1
        assert items[0].title == "重复帖子-更新标题"
        assert items[0].excerpt == "second snapshot"
        assert items[0].first_seen_job_id == first_job.id
        assert items[0].last_seen_job_id == second_job.id


def test_report_service_preserves_date_only_published_at_without_midnight_display(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "report-service-date-only.db")

    with session_factory() as session:
        source = create_source(session, "日期来源", "https://example.com/source-date-only")
        job = JobService(session).create_manual_job()

        report = ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "只有日期的帖子",
                            "url": "https://example.com/date-only-post",
                            "published_at": "2026-03-24",
                        }
                    ],
                }
            ],
        )

        markdown = Path(report.markdown_path).read_text(encoding="utf-8")

        assert "- [NEW] [只有日期的帖子](https://example.com/date-only-post) - 2026-03-24" in markdown
        assert "2026-03-24 00:00" not in markdown


def test_report_service_does_not_mark_items_missing_when_source_failed_in_current_job(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "report-service-failed-source-not-missing.db")

    with session_factory() as session:
        source = create_source(session, "失败来源", "https://space.bilibili.com/20411266")
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        service = ReportService(session)

        service.generate_for_job(
            first_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "历史命中视频",
                            "url": "https://www.bilibili.com/video/BV1REAL",
                            "published_at": "2026-03-24 08:00",
                        }
                    ],
                }
            ],
        )

        session.add(
            JobLog(
                job_id=second_job.id,
                source_id=source.id,
                level="error",
                message="bilibili profile page redirected to unexpected url (可能触发风控或登录失效): https://member.bilibili.com/platform/upload/video/frame",
            )
        )
        session.flush()

        second_report = service.generate_for_job(second_job, [])
        second_markdown = Path(second_report.markdown_path).read_text(encoding="utf-8")

        assert "[本次未抓到] [历史命中视频](https://www.bilibili.com/video/BV1REAL)" not in second_markdown
        assert "- [历史命中视频](https://www.bilibili.com/video/BV1REAL) - 2026-03-24 08:00" in second_markdown
        assert "redirected to unexpected url" in second_markdown


def test_report_service_keeps_previous_global_markdown_when_commit_fails(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "report-service-commit-rollback.db")

    with session_factory() as session:
        source = create_source(session, "原子来源", "https://example.com/source-atomic")
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        service = ReportService(session)

        first_report = service.generate_for_job(
            first_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "首次成功帖子",
                            "url": "https://example.com/atomic-post-1",
                            "published_at": "2026-03-24 08:00",
                        }
                    ],
                }
            ],
        )
        markdown_path = Path(first_report.markdown_path)
        docx_path = Path(first_report.docx_path)
        old_markdown = markdown_path.read_text(encoding="utf-8")
        old_docx = docx_path.read_bytes()

        def fail_commit() -> None:
            raise RuntimeError("commit failed after files ready")

        monkeypatch.setattr(session, "commit", fail_commit)

        with pytest.raises(RuntimeError, match="commit failed after files ready"):
            service.generate_for_job(
                second_job,
                [
                    {
                        "source_id": source.id,
                        "source_name": source.name,
                        "items": [
                            {
                                "title": "第二次失败帖子",
                                "url": "https://example.com/atomic-post-2",
                                "published_at": "2026-03-24 09:00",
                            }
                        ],
                    }
                ],
            )

        current_markdown = markdown_path.read_text(encoding="utf-8")
        current_docx = docx_path.read_bytes()
        assert current_markdown == old_markdown
        assert current_docx == old_docx
        assert "第二次失败帖子" not in current_markdown


def test_report_service_restores_both_files_when_second_activation_step_fails(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "report-service-activation-rollback.db")

    with session_factory() as session:
        source = create_source(session, "激活来源", "https://example.com/source-activation")
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        service = ReportService(session)

        first_report = service.generate_for_job(
            first_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "首次成功帖子",
                            "url": "https://example.com/activation-post-1",
                            "published_at": "2026-03-24 08:00",
                        }
                    ],
                }
            ],
        )
        markdown_path = Path(first_report.markdown_path)
        docx_path = Path(first_report.docx_path)
        old_markdown = markdown_path.read_text(encoding="utf-8")
        old_docx = docx_path.read_bytes()
        original_replace = service._replace_report_file
        call_count = {"value": 0}

        def fail_on_second_activation(target_path: Path, temp_path: Path, backup_path: Path) -> None:
            call_count["value"] += 1
            if call_count["value"] == 1:
                original_replace(target_path, temp_path, backup_path)
                return

            backup_path.unlink(missing_ok=True)
            backup_created = False
            if target_path.exists():
                target_path.replace(backup_path)
                backup_created = True
            try:
                raise RuntimeError("docx activation failed")
            except Exception:
                if backup_created and backup_path.exists():
                    target_path.unlink(missing_ok=True)
                    backup_path.replace(target_path)
                raise

        monkeypatch.setattr(service, "_replace_report_file", fail_on_second_activation)

        with pytest.raises(RuntimeError, match="docx activation failed"):
            service.generate_for_job(
                second_job,
                [
                    {
                        "source_id": source.id,
                        "source_name": source.name,
                        "items": [
                            {
                                "title": "第二次失败帖子",
                                "url": "https://example.com/activation-post-2",
                                "published_at": "2026-03-24 09:00",
                            }
                        ],
                    }
                ],
            )

        current_markdown = markdown_path.read_text(encoding="utf-8")
        current_docx = docx_path.read_bytes()
        assert current_markdown == old_markdown
        assert current_docx == old_docx


def test_report_service_rolls_back_when_upsert_collected_items_fails(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "report-service-upsert-rollback.db")

    with session_factory() as session:
        source = create_source(session, "回滚来源", "https://example.com/source-rollback")
        job = JobService(session).create_manual_job()
        service = ReportService(session)

        rollback_called = {"called": False}
        original_rollback = session.rollback

        def fail_upsert(current_job: CollectionJob, source_runs: list[dict[str, object]]) -> None:
            raise RuntimeError("upsert failed")

        def track_rollback() -> None:
            rollback_called["called"] = True
            original_rollback()

        monkeypatch.setattr(service, "_upsert_collected_items", fail_upsert)
        monkeypatch.setattr(session, "rollback", track_rollback)

        with pytest.raises(RuntimeError, match="upsert failed"):
            service.generate_for_job(
                job,
                [
                    {
                        "source_id": source.id,
                        "source_name": source.name,
                        "items": [],
                    }
                ],
            )

        assert rollback_called["called"] is True




def test_report_service_downloads_item_images_into_markdown_and_docx(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "report-service-images.db")

    stale_asset = Path(os.environ["REPORTS_ROOT"]) / "global" / "assets" / "stale.png"
    stale_asset.parent.mkdir(parents=True, exist_ok=True)
    stale_asset.write_bytes(TINY_PNG_BYTES)

    with session_factory() as session:
        source = create_source(session, "图片来源", "https://example.com/source-images")
        job = JobService(session).create_manual_job()

        def fake_download_image_asset(self, image_url: str, destination_path: Path) -> Path:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(TINY_PNG_BYTES)
            return destination_path

        monkeypatch.setattr(ReportService, "_download_image_asset", fake_download_image_asset)

        report = ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "带图片帖子",
                            "url": "https://example.com/post-with-image",
                            "published_at": "2026-03-24 08:00",
                            "image_urls": ["https://example.com/media/post-image-1.png"],
                        }
                    ],
                }
            ],
        )

        item = session.scalar(select(CollectedItem))
        markdown = Path(report.markdown_path).read_text(encoding="utf-8")

        assert item is not None
        assert item.image_urls == ["https://example.com/media/post-image-1.png"]
        assert stale_asset.exists() is False
        assert "![](assets/" in markdown

        with ZipFile(report.docx_path) as archive:
            assert any(name.startswith("word/media/") for name in archive.namelist())
