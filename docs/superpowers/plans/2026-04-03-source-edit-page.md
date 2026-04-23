# Source Edit Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为来源详情提供完整的常用字段编辑页，并让列表页和详情页都能进入编辑、保存后回到列表并显示成功提示。

**Architecture:** 继续沿用现有服务层和页面路由结构，在 `SourceService` 增加显式读取接口，页面路由只负责渲染和表单解析，不再通过“空更新”间接读取来源。测试先覆盖服务层读取和页面保存流程，再以最小实现让它们通过。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest

---

### Task 1: 固化编辑页范围

**Files:**
- Create: `docs/superpowers/plans/2026-04-03-source-edit-page.md`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: 确认编辑页只开放常用字段的测试**

```python
def test_source_edit_page_shows_common_edit_fields(tmp_path) -> None:
    response = client.get(f"/sources/{created['id']}")
    assert "name='name'" in response.text
    assert "name='entry_url'" in response.text
    assert "name='search_keyword'" in response.text
    assert "name='source_group'" in response.text
    assert "name='max_items'" in response.text
    assert "name='enabled'" in response.text
    assert "name='fetch_mode'" not in response.text
```

- [ ] **Step 2: 运行页面测试确认当前行为**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\integration\\test_pages.py -k "source_edit_page or source_saved_message or sources_page_lists_sources_and_actions or saving_source_edit" -v`
Expected: 编辑页相关用例全部通过，作为后续重构保护网。

### Task 2: 用显式读取接口替换错误实现

**Files:**
- Modify: `tests/unit/test_source_service.py`
- Modify: `app/services/source_service.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: 先写读取接口的失败测试**

```python
def test_source_service_gets_source_by_id(tmp_path) -> None:
    service = SourceService(session)
    source = service.get_source(str(created.id))
    assert source is not None
    assert source.name == "国内来源"
```

- [ ] **Step 2: 运行单测确认当前失败**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_source_service.py -k get_source -v`
Expected: FAIL，提示 `SourceService` 尚无 `get_source`。

- [ ] **Step 3: 实现最小读取逻辑并替换页面调用**

```python
def get_source(self, source_id: str) -> Source | None:
    return self.session.get(Source, UUID(source_id))
```

```python
source = SourceService(session).get_source(source_id)
if source is None:
    raise HTTPException(status_code=404, detail="source not found")
```

- [ ] **Step 4: 运行单测确认读取接口通过**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_source_service.py -k get_source -v`
Expected: PASS

### Task 3: 回归编辑页保存流程

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: 运行编辑页相关集成测试**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\integration\\test_pages.py -k "source_edit_page or source_saved_message or sources_page_lists_sources_and_actions or saving_source_edit" -v`
Expected: PASS

- [ ] **Step 2: 运行服务层与页面回归测试**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_source_service.py tests\\integration\\test_pages.py tests\\integration\\test_sources_api.py -v`
Expected: PASS

- [ ] **Step 3: 运行应用导入链检查**

Run: `.\\.venv\\Scripts\\python.exe -c "import launcher; from app.main import create_app; create_app(start_background_workers=False); print('ok')"`
Expected: 输出 `ok`
