# 采集源国内国外分组与手动分组采集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让采集源支持手动分为国内/国外，首页可分别触发国内或国外的立即采集，`/sources` 页面按分组展示，并在 `/scheduler` 页面增加返回首页按钮。

**Architecture:** 在 `Source` 数据模型中增加 `source_group` 字段，在 `CollectionJob` 中增加任务执行范围字段，让手动任务可以绑定到国内或国外。页面层把首页入口拆成两个明确的分组按钮，把来源管理页分成国内、国外、未分组三块展示，并在调度页头部增加回首页动作；定时调度继续复用全量执行逻辑，不受分组影响。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest

---

| 文件 | 动作 | 责任 |
|---|---|---|
| `app/models/source.py` | Modify | 为采集源新增 `source_group` 字段 |
| `app/models/job.py` | Modify | 为任务新增手动执行范围字段 |
| `app/schemas/source.py` | Modify | 来源创建/更新/读取增加分组字段与枚举 |
| `app/services/source_service.py` | Modify | 提供按分组统计、分组列表与旧数据兼容行为 |
| `app/services/job_service.py` | Modify | 增加按分组创建手动任务方法 |
| `app/workers/runner.py` | Modify | 按任务范围只执行对应分组来源 |
| `app/api/routes_sources.py` | Modify | 来源表单/API 支持分组字段 |
| `app/api/routes_pages.py` | Modify | 首页双按钮、来源页分组展示、调度页返回首页按钮、按分组运行路由 |
| `tests/unit/test_models.py` | Modify | 验证新增模型字段存在 |
| `tests/unit/test_source_service.py` | Create/Modify | 覆盖分组列表与统计 |
| `tests/unit/test_job_service.py` | Create/Modify | 覆盖按分组创建任务 |
| `tests/unit/test_runner.py` | Modify | 覆盖按任务范围筛选来源 |
| `tests/integration/test_sources_api.py` | Modify | 覆盖来源分组字段必填、读写、表单创建 |
| `tests/integration/test_pages.py` | Modify | 覆盖首页双按钮、来源页分组、调度页返回首页 |
| `docs/superpowers/specs/2026-04-03-source-grouped-manual-runs-design.md` | Reference | 本次实现依据 |

### Task 1: 数据模型与 Schema

**Files:**
- Modify: `tests/unit/test_models.py`
- Modify: `app/models/source.py`
- Modify: `app/models/job.py`
- Modify: `app/schemas/source.py`

- [ ] **Step 1: 写失败测试，断言 `Source` 有 `source_group` 字段，`CollectionJob` 有任务范围字段**

```python
def test_source_model_includes_source_group_column() -> None:
    columns = Source.__table__.columns
    assert "source_group" in columns


def test_collection_job_model_includes_source_group_scope_column() -> None:
    columns = CollectionJob.__table__.columns
    assert "source_group_scope" in columns
```

- [ ] **Step 2: 运行模型测试，确认当前失败**

Run: `pytest tests/unit/test_models.py -v`
Expected: FAIL，因为新增字段尚不存在。

- [ ] **Step 3: 最小实现模型字段与 Schema 枚举**

```python
SourceGroup = Literal["domestic", "overseas"]

source_group: Mapped[str | None] = mapped_column(String(20), nullable=True)
source_group_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

- [ ] **Step 4: 在 `SourceCreate` 中把 `source_group` 设为必填，在 `SourceUpdate/SourceRead` 中补齐**

- [ ] **Step 5: 重新运行模型测试，确认通过**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS

### Task 2: 服务层支持按分组统计与运行

**Files:**
- Modify: `tests/unit/test_source_service.py`
- Modify: `tests/unit/test_job_service.py`
- Modify: `tests/unit/test_runner.py`
- Modify: `app/services/source_service.py`
- Modify: `app/services/job_service.py`
- Modify: `app/workers/runner.py`

- [ ] **Step 1: 写失败测试，验证可按 `domestic` / `overseas` 列出与统计来源**

```python
def test_source_service_counts_enabled_sources_by_group(session) -> None:
    ...
    assert service.count_enabled_sources("domestic") == 1
```

- [ ] **Step 2: 写失败测试，验证 `create_manual_job_for_group("domestic")` 只统计国内来源**

```python
def test_job_service_creates_manual_job_for_domestic_group(session) -> None:
    job = JobService(session).create_manual_job_for_group("domestic")
    assert job.source_group_scope == "domestic"
    assert job.total_sources == 1
```

- [ ] **Step 3: 写失败测试，验证 `JobRunner` 只执行任务范围对应的来源**

```python
def test_runner_executes_only_sources_in_job_scope(session_factory) -> None:
    ...
    assert executed_names == ["国内来源A"]
```

- [ ] **Step 4: 运行聚焦单元测试，确认失败**

Run: `pytest tests/unit/test_source_service.py tests/unit/test_job_service.py tests/unit/test_runner.py -v`
Expected: FAIL，因为服务与执行器尚不支持分组。

- [ ] **Step 5: 最小实现 `SourceService` 的分组筛选与统计辅助方法**

```python
def list_sources_by_group(self, group: str | None) -> list[Source]:
    ...

def count_enabled_sources(self, group: str | None) -> int:
    ...
```

- [ ] **Step 6: 最小实现 `JobService.create_manual_job_for_group()`，保留原有全量方法**

- [ ] **Step 7: 最小实现 `JobRunner` 根据 `job.source_group_scope` 筛选来源**

- [ ] **Step 8: 重新运行聚焦单元测试，确认通过**

Run: `pytest tests/unit/test_source_service.py tests/unit/test_job_service.py tests/unit/test_runner.py -v`
Expected: PASS

### Task 3: 来源 API 与表单分组字段

**Files:**
- Modify: `tests/integration/test_sources_api.py`
- Modify: `app/api/routes_sources.py`

- [ ] **Step 1: 写失败测试，验证简化来源表单必须提供 `source_group`**

```python
def test_create_source_form_requires_source_group(tmp_path) -> None:
    response = client.post("/api/sources/form", data={...})
    assert response.status_code == 422
```

- [ ] **Step 2: 写失败测试，验证来源读取会返回 `source_group`**

```python
def test_create_source_returns_source_group(tmp_path) -> None:
    ...
    assert data["source_group"] == "domestic"
```

- [ ] **Step 3: 运行聚焦 API 测试，确认失败**

Run: `pytest tests/integration/test_sources_api.py -k "source_group" -v`
Expected: FAIL

- [ ] **Step 4: 最小实现来源 API 表单与读写支持**

```python
source_group = _normalize_optional_text(_get_form_value(form_data, "source_group"))
...
return SourceCreate(..., source_group=source_group)
```

- [ ] **Step 5: 重新运行聚焦 API 测试，确认通过**

Run: `pytest tests/integration/test_sources_api.py -k "source_group" -v`
Expected: PASS

### Task 4: 首页双按钮、来源页分组展示、调度页返回首页

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: 写失败测试，验证首页显示“立即采集国内”“立即采集国外”两个按钮**

```python
def test_index_page_shows_grouped_run_buttons(tmp_path) -> None:
    response = client.get("/")
    assert "/jobs/run/domestic" in response.text
    assert "/jobs/run/overseas" in response.text
```

- [ ] **Step 2: 写失败测试，验证 `/sources` 页面拆成国内、国外、未分组三块**

```python
def test_sources_page_groups_sources_by_source_group(tmp_path) -> None:
    ...
    assert "国内采集源" in response.text
    assert "国外采集源" in response.text
    assert "未分组采集源" in response.text
```

- [ ] **Step 3: 写失败测试，验证 `/scheduler` 页面有“返回首页”按钮**

```python
def test_scheduler_page_shows_back_to_home_button(tmp_path) -> None:
    response = client.get("/scheduler")
    assert "返回首页" in response.text
    assert "href='/'" in response.text
```

- [ ] **Step 4: 运行聚焦页面测试，确认失败**

Run: `pytest tests/integration/test_pages.py -k "grouped_run_buttons or groups_sources_by_source_group or back_to_home_button" -v`
Expected: FAIL

- [ ] **Step 5: 最小实现首页动作区、来源页分组 panel 和调度页返回首页按钮**

- [ ] **Step 6: 重新运行聚焦页面测试，确认通过**

Run: `pytest tests/integration/test_pages.py -k "grouped_run_buttons or groups_sources_by_source_group or back_to_home_button" -v`
Expected: PASS

### Task 5: 按分组手动运行入口

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: 写失败测试，验证点击 `/jobs/run/domestic` 只创建国内任务**

```python
def test_post_run_domestic_job_creates_domestic_scoped_job(tmp_path) -> None:
    response = client.post("/jobs/run/domestic", follow_redirects=False)
    assert response.status_code == 303
```

- [ ] **Step 2: 写失败测试，验证分组没有启用来源时不创建空任务**

```python
def test_post_run_overseas_job_without_enabled_sources_does_not_create_job(tmp_path) -> None:
    response = client.post("/jobs/run/overseas", follow_redirects=False)
    assert response.status_code == 303
```

- [ ] **Step 3: 运行聚焦页面/集成测试，确认失败**

Run: `pytest tests/integration/test_pages.py -k "run_domestic_job or run_overseas_job" -v`
Expected: FAIL

- [ ] **Step 4: 最小实现 `/jobs/run/domestic`、`/jobs/run/overseas` 路由与空分组提示**

```python
job = JobService(session).create_manual_job_for_group("domestic")
if job is None:
    return RedirectResponse(url="/?run_group_empty=domestic", status_code=303)
```

- [ ] **Step 5: 重新运行聚焦测试，确认通过**

Run: `pytest tests/integration/test_pages.py -k "run_domestic_job or run_overseas_job" -v`
Expected: PASS

### Task 6: 全量回归

**Files:**
- Modify: `docs/superpowers/specs/2026-04-03-source-grouped-manual-runs-design.md` (only if needed for terminology sync)

- [ ] **Step 1: 运行本次相关测试全集**

Run: `pytest tests/unit/test_models.py tests/unit/test_source_service.py tests/unit/test_job_service.py tests/unit/test_runner.py tests/integration/test_sources_api.py tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 2: 启动应用做导入链验证**

Run: `.\\.venv\\Scripts\\python.exe -c "import launcher; from app.main import create_app; create_app(start_background_workers=False); print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 3: 检查术语一致性**

核对页面文案统一为：
- `国内`
- `国外`
- `未分组`
- `立即采集国内`
- `立即采集国外`
- `返回首页`
