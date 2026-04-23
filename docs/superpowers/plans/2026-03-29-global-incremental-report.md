# Global Incremental Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前“一任务一报告”改为“全系统单总报告”，并在每轮重建时对本次新增条目标记 `NEW`、对历史但本次未命中的条目标记“本次未抓到”。

**Architecture:** 继续沿用 FastAPI + SQLAlchemy + 文件落盘的架构，不做文本级增量拼接，而是先把抓取结果沉淀到 `collected_items` 历史表，再由 `ReportService` 基于数据库状态完整重建同一份 Markdown/DOCX 总报告。页面层和任务详情页不再按 `job_id` 查专属报告，而是统一跳转这条全局报告记录。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy ORM, SQLite compatibility patching, pytest integration/unit tests

---

## File Map

| 文件 | 责任 |
|---|---|
| `app/models/item.py` | 历史条目状态字段：首次发现、最近命中、最近任务 |
| `app/models/report.py` | 报告记录语义调整为单总报告 |
| `app/db.py` | SQLite 旧库补列兼容 |
| `app/services/report_service.py` | 历史条目 upsert、全局报告查询、总报告重建 |
| `app/workers/runner.py` | 任务完成后调用总报告重建链路 |
| `app/services/job_service.py` | 从“按任务查报告”改为“返回全局报告 ID” |
| `app/api/routes_reports.py` | 报告列表/详情页适配单总报告语义 |
| `app/api/routes_pages.py` | 首页、任务详情页、进度面板链接统一指向全局报告 |
| `tests/unit/test_models.py` | 模型字段与外键语义断言 |
| `tests/unit/test_report_service.py` | 报告重建、`NEW`、未命中、单记录复用 |
| `tests/integration/test_reports.py` | 连续两次任务后的报告内容与页面行为 |
| `tests/integration/test_pages.py` | 首页/任务详情继续能打开同一份全局报告 |

## Implementation Notes

| 约束 | 说明 |
|---|---|
| 报告文件路径 | 固定到单一路径，例如 `outputs/reports/global/hot-report.md` 与 `outputs/reports/global/hot-report.docx` |
| `NEW` 语义 | 仅当 `first_seen_job_id == current_job.id` 时显示 |
| “本次未抓到”语义 | 条目存在于历史表，但 `last_seen_job_id != current_job.id` |
| 页面兼容 | 历史任务详情页的“查看报告”都跳向同一全局报告 |
| 旧库兼容 | 沿用 `ensure_schema_compatibility()` 的思路，为 SQLite 增补新列 |

### Task 1: Expand persistence model for historical item state

**Files:**
- Modify: `app/models/item.py`
- Modify: `app/models/report.py`
- Modify: `app/db.py`
- Test: `tests/unit/test_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
def test_collected_item_tracks_first_and_last_seen_fields() -> None:
    columns = CollectedItem.__table__.columns

    assert "first_seen_at" in columns
    assert "last_seen_at" in columns
    assert "first_seen_job_id" in columns
    assert "last_seen_job_id" in columns


def test_report_latest_job_id_is_optional_or_tracks_latest_update() -> None:
    columns = Report.__table__.columns

    assert "markdown_path" in columns
    assert "docx_path" in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\unit\test_models.py -q`
Expected: FAIL because new item/report fields are not defined yet.

- [ ] **Step 3: Write minimal model implementation**

```python
class CollectedItem(Base):
    first_seen_job_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=True)
    last_seen_job_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```python
_SQLITE_LEGACY_ITEM_COLUMN_PATCHES = (
    ("first_seen_job_id", "ALTER TABLE collected_items ADD COLUMN first_seen_job_id CHAR(32)"),
    ("last_seen_job_id", "ALTER TABLE collected_items ADD COLUMN last_seen_job_id CHAR(32)"),
    ("first_seen_at", "ALTER TABLE collected_items ADD COLUMN first_seen_at DATETIME"),
    ("last_seen_at", "ALTER TABLE collected_items ADD COLUMN last_seen_at DATETIME"),
)
```

实现要点：
- `Report` 模型尽量少改动；如保留 `job_id`，其语义改为“最近更新该总报告的任务 ID”。
- `ensure_schema_compatibility()` 除 `sources` 外，还要检查 `collected_items` 与 `reports` 必要字段。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\unit\test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models/item.py app/models/report.py app/db.py tests/unit/test_models.py
git commit -m "feat: add historical item state fields"
```

### Task 2: Persist collected items and rebuild a single global report

**Files:**
- Modify: `app/services/report_service.py`
- Modify: `app/workers/runner.py`
- Test: `tests/unit/test_report_service.py`

- [ ] **Step 1: Write the failing report service tests**

```python
def test_runner_reuses_single_global_report_and_marks_new_items(tmp_path) -> None:
    report = run_job_with_items(tmp_path, [
        {"title": "首发内容", "url": "https://example.com/post-1", "published_at": "2026-03-24 08:00"},
    ])

    markdown_text = Path(report.markdown_path).read_text(encoding="utf-8")
    assert "[NEW] 首发内容" in markdown_text


def test_second_run_marks_missing_items_without_creating_second_report(tmp_path) -> None:
    first_report_id = run_job_with_items(tmp_path, [{"title": "A", "url": "https://example.com/a"}]).id
    second_report = run_job_with_items(tmp_path, [])

    assert second_report.id == first_report_id
    markdown_text = Path(second_report.markdown_path).read_text(encoding="utf-8")
    assert "[本次未抓到] A" in markdown_text
    assert "[NEW] A" not in markdown_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\unit\test_report_service.py -q`
Expected: FAIL because service still creates per-job reports and does not persist item history.

- [ ] **Step 3: Write minimal implementation**

先把 `ReportService.generate_for_job()` 拆成两个内部步骤：

```python
def generate_for_job(self, job: CollectionJob, source_runs: list[dict[str, object]]) -> Report:
    self._upsert_collected_items(job, source_runs)
    return self._rebuild_global_report(job)
```

建议的最小实现骨架：

```python
def _upsert_collected_items(self, job: CollectionJob, source_runs: list[dict[str, object]]) -> None:
    seen_hashes: set[str] = set()
    for run in source_runs:
        source = self._get_source_by_name(run["source_name"])
        for item in run.get("items", []) or []:
            normalized_hash = self._normalize_item_hash(source.id, item)
            seen_hashes.add(normalized_hash)
            stored = self.session.scalar(select(CollectedItem).where(CollectedItem.normalized_hash == normalized_hash))
            if stored is None:
                stored = CollectedItem(
                    source_id=source.id,
                    job_id=job.id,
                    first_seen_job_id=job.id,
                    last_seen_job_id=job.id,
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                    title=item.get("title") or "未命名帖子",
                    url=item.get("url") or "",
                    normalized_hash=normalized_hash,
                )
                self.session.add(stored)
            else:
                stored.last_seen_job_id = job.id
                stored.last_seen_at = datetime.utcnow()
                stored.title = item.get("title") or stored.title
                stored.url = item.get("url") or stored.url
```

```python
def _rebuild_global_report(self, job: CollectionJob) -> Report:
    report_dir = get_reports_root() / "global"
    markdown_path = report_dir / "hot-report.md"
    docx_path = report_dir / "hot-report.docx"
    markdown_content = self._build_global_markdown(job)
    markdown_path.write_text(markdown_content, encoding="utf-8")
    self._write_docx(docx_path, markdown_content)
    report = self._get_or_create_global_report(job, markdown_path, docx_path)
    self.session.commit()
    self.session.refresh(report)
    return report
```

```python
def _build_global_markdown(self, job: CollectionJob) -> str:
    items = self._list_items_grouped_by_source()
    # current job: first_seen_job_id == job.id => NEW
    # current job: last_seen_job_id != job.id => 本次未抓到
```

同时修改 `JobRunner.run_once()` 让它仍然只在任务结束后调一次 `ReportService(session).generate_for_job(job, source_runs)`，不新增第二条报告链路。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\unit\test_report_service.py -q`
Expected: PASS with one report record reused across multiple runs.

- [ ] **Step 5: Commit**

```bash
git add app/services/report_service.py app/workers/runner.py tests/unit/test_report_service.py
git commit -m "feat: rebuild a single global report from historical items"
```

### Task 3: Switch report lookup and pages to the global report

**Files:**
- Modify: `app/services/job_service.py`
- Modify: `app/api/routes_reports.py`
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_reports.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing page/integration tests**

```python
def test_reports_page_shows_single_global_report_after_two_runs(tmp_path, monkeypatch) -> None:
    first_id = run_collection_once(...)
    second_id = run_collection_once(...)

    reports_page = client.get("/reports")
    assert reports_page.text.count("/reports/") == 1
    assert "全局热点总报告" in reports_page.text
```

```python
def test_job_detail_uses_global_report_id_for_any_job(tmp_path, monkeypatch) -> None:
    first_job_id, global_report_id = run_collection_once(...)
    second_job_id, same_report_id = run_collection_once(...)

    assert same_report_id == global_report_id
    detail_page = client.get(f"/jobs/{first_job_id}")
    assert f"/reports/{global_report_id}" in detail_page.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\integration\test_reports.py tests\integration\test_pages.py -q`
Expected: FAIL because `JobService.get_report_id()` still uses `job_id` and reports page still lists multiple reports.

- [ ] **Step 3: Write minimal implementation**

```python
class JobService:
    def get_report_id(self, job_id: str) -> UUID | None:
        report = self.session.scalar(select(Report).order_by(Report.created_at.desc()).limit(1))
        return None if report is None else report.id
```

```python
class ReportService:
    def get_global_report(self) -> Report | None:
        return self.session.scalar(select(Report).order_by(Report.created_at.desc()).limit(1))
```

`routes_reports.py` 调整点：
- `/reports` 页面只渲染这一条总报告。
- 标题改成“总报告”或“全局热点总报告”。
- 下载接口仍复用 `/api/reports/{report_id}/download`。

`routes_pages.py` 调整点：
- 首页、任务详情、进度面板继续调用 `get_report_id()`，但得到的是同一个全局报告 ID。
- 报告入口文案从“历史报告”可改为“总报告”，但不是必须；先以行为正确为主。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\integration\test_reports.py tests\integration\test_pages.py -q`
Expected: PASS, and all report links point to the same report record.

- [ ] **Step 5: Commit**

```bash
git add app/services/job_service.py app/api/routes_reports.py app/api/routes_pages.py tests/integration/test_reports.py tests/integration/test_pages.py
git commit -m "feat: point pages and report routes to the global report"
```

### Task 4: Add regression coverage for status transitions across runs

**Files:**
- Modify: `tests/unit/test_report_service.py`
- Modify: `tests/integration/test_reports.py`

- [ ] **Step 1: Write the failing regression tests**

```python
def test_second_run_keeps_old_item_without_new_marker(tmp_path) -> None:
    run_job_with_items(tmp_path, [{"title": "老帖子", "url": "https://example.com/old"}])
    report = run_job_with_items(tmp_path, [{"title": "老帖子", "url": "https://example.com/old"}])

    markdown_text = Path(report.markdown_path).read_text(encoding="utf-8")
    assert "[NEW] 老帖子" not in markdown_text
    assert "老帖子" in markdown_text
```

```python
def test_report_contains_new_and_missing_sections_in_same_run(tmp_path, monkeypatch) -> None:
    run_collection_once_with_fixture("first.html")
    report_id = run_collection_once_with_fixture("second.html")

    detail_page = client.get(f"/reports/{report_id}")
    assert "[NEW] 第二轮新增" in detail_page.text
    assert "[本次未抓到] 第一轮内容" in detail_page.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\unit\test_report_service.py tests\integration\test_reports.py -q`
Expected: FAIL until ordering and marker rules are fully implemented.

- [ ] **Step 3: Write minimal implementation**

补齐 `_build_global_markdown()` 的排序与标记逻辑：

```python
def _item_marker(item: CollectedItem, current_job_id) -> str:
    if item.first_seen_job_id == current_job_id:
        return "[NEW] "
    if item.last_seen_job_id != current_job_id:
        return "[本次未抓到] "
    return ""
```

```python
def _sort_key(item: CollectedItem, current_job_id):
    is_new = item.first_seen_job_id == current_job_id
    last_seen = item.last_seen_at or datetime.min
    return (0 if is_new else 1, -last_seen.timestamp())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\unit\test_report_service.py tests\integration\test_reports.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_report_service.py tests/integration/test_reports.py app/services/report_service.py
git commit -m "test: lock global report status transitions"
```

### Task 5: Run full verification for touched areas

**Files:**
- Test: `tests/unit/test_models.py`
- Test: `tests/unit/test_report_service.py`
- Test: `tests/integration/test_reports.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Run focused unit tests**

Run: `python -m pytest tests\unit\test_models.py tests\unit\test_report_service.py -q`
Expected: PASS.

- [ ] **Step 2: Run focused integration tests**

Run: `python -m pytest tests\integration\test_reports.py tests\integration\test_pages.py -q`
Expected: PASS.

- [ ] **Step 3: Run the full relevant suite**

Run: `python -m pytest -q`
Expected: PASS, or explicitly capture any unrelated pre-existing failures before merge.

- [ ] **Step 4: Review resulting behavior manually in HTML output if needed**

Checkpoints:
- `/reports` 只有一条总报告入口
- 任意任务详情页都能打开同一份报告
- 第二轮新增条目显示 `NEW`
- 第一轮存在但第二轮未命中的条目显示“本次未抓到”

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: support global incremental report workflow"
```

## Risks To Watch During Execution

| 风险 | 具体点 |
|---|---|
| `normalized_hash` 生成缺位 | 当前执行链路里还没有现成通用 hash 生成逻辑，执行时需要先统一规则，优先基于 `source_id + url`，缺 URL 时退化到 `source_id + title + published_at` |
| 旧库兼容 | SQLite 只能 `ADD COLUMN`，不要计划中引入需要直接删除或重命名列的迁移 |
| `job_id` 语义混乱 | `CollectedItem.job_id` 与新引入的 `first_seen_job_id / last_seen_job_id` 需要在实现时明确保留语义，避免未来误用 |
| 页面文案 | 如果保留“历史报告”文案，行为上仍正确，但产品表达会显得不一致；可放在实现末尾视情况微调 |

## Out Of Scope During Execution

| 不做项 | 原因 |
|---|---|
| 保留历史任务快照报告 | 需求明确改为单总报告 |
| 新增复杂筛选页 | 当前只需要稳定生成与展示 |
| 对旧报告做批量数据迁移 UI | 当前不是用户显性需求 |
