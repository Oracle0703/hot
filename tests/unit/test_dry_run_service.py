"""TC-STRAT-301~302 — 试抓服务单元测试。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.dry_run_service import DEFAULT_DRY_RUN_LIMIT, DryRunService


@dataclass
class _FakeSource:
    list_selector: str = "li.item"
    title_selector: str = ".t"
    link_selector: str = "a"
    meta_selector: str | None = None
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    max_items: int = 30


def _make_html(n: int) -> str:
    rows = "".join(
        f'<li class="item"><span class="t">title-{i}</span><a href="https://x/{i}">go</a></li>'
        for i in range(n)
    )
    return f"<html><body><ul>{rows}</ul></body></html>"


def test_dry_run_caps_items_to_five() -> None:
    """TC-STRAT-301"""
    service = DryRunService(fetcher=lambda s: _make_html(20))
    result = service.dry_run(_FakeSource())
    assert len(result.items) == DEFAULT_DRY_RUN_LIMIT == 5
    assert result.diagnostics["list_hits"] >= 20
    assert result.diagnostics["kept_total"] >= 5


def test_dry_run_includes_diagnostics() -> None:
    """TC-STRAT-302"""
    src = _FakeSource(include_keywords=["title-1"])  # 命中 title-1, title-10..19 = 11 条
    service = DryRunService(fetcher=lambda s: _make_html(20))
    result = service.dry_run(src)
    diag = result.diagnostics
    for key in ("list_hits", "title_hits", "filtered_out", "capped_to", "kept_total"):
        assert key in diag, key
    # 截断后不超过 5
    assert len(result.items) <= DEFAULT_DRY_RUN_LIMIT


def test_dry_run_reports_zero_hits_for_wrong_selector() -> None:
    """TC-STRAT-102"""
    src = _FakeSource(list_selector=".missing")
    service = DryRunService(fetcher=lambda s: _make_html(3))

    result = service.dry_run(src)

    assert result.items == []
    assert result.diagnostics["list_hits"] == 0
    assert result.diagnostics["title_hits"] == 0
