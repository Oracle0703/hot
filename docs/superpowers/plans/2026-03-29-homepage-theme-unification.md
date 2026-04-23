# Homepage Theme Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将首页现有深色风格统一到来源管理、任务详情、调度页和报告页，同时保持所有业务行为、路由与交互逻辑不变。

**Architecture:** 继续复用 `app/ui/page_theme.py` 作为唯一主题入口，先用测试锁定新的统一外壳和报告页结构，再最小化修改 `routes_pages.py` 与 `routes_reports.py`，把原本的浅色页面和裸 HTML 页面迁移到首页同一套深色页面壳。所有改动限制在服务端 HTML 输出和共享 CSS，不触碰服务层、模型层和 API 协议。

**Tech Stack:** FastAPI, Python server-rendered HTML, pytest

---

## File Structure

| Path | Action | Responsibility |
| --- | --- | --- |
| `tests/integration/test_pages.py` | Modify | 为统一后的内页深色主题与报告页页面壳添加失败测试 |
| `app/ui/page_theme.py` | Modify | 扩展深色全站样式，补齐表单、日志、报告预览等通用样式 |
| `app/api/routes_pages.py` | Modify | 将 `/sources`、`/sources/new`、`/jobs/{id}`、`/scheduler` 切到首页主题 |
| `app/api/routes_reports.py` | Modify | 将 `/reports` 与 `/reports/{id}` 从裸 HTML 迁移到统一页面壳 |
| `docs/superpowers/specs/2026-03-29-homepage-theme-unification-design.md` | Keep | 已确认的设计基线 |
| `docs/superpowers/plans/2026-03-29-homepage-theme-unification.md` | Create | 本实现计划 |

## Execution Notes

- 当前目录不是 git 仓库，因此计划中的提交步骤只作为检查点记录，不执行 `git commit`。
- 按 TDD 执行：先写失败测试，确认失败原因正确，再写最小实现，再跑通过验证。
- 不改任何业务接口、路由、表单字段名、自动刷新脚本和报告下载接口。

### Task 1: 锁定统一后的页面行为测试

**Files:**
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: 为来源管理页添加深色主题断言**

在 `test_sources_page_lists_sources_and_actions` 中增加对统一主题的断言，例如：

```python
assert "theme-dark" in response.text
assert "app-shell" in response.text
assert "page-header" in response.text
```

- [ ] **Step 2: 运行来源管理页测试并确认失败**

Run: `python -m pytest tests\integration\test_pages.py -k sources_page -q`
Expected: FAIL，因为当前 `/sources` 仍返回 `theme-light`。

- [ ] **Step 3: 为新增来源页添加深色主题断言**

在 `test_new_source_page_shows_simplified_source_form_fields` 中增加断言：

```python
assert "theme-dark" in response.text
assert "app-shell" in response.text
```

- [ ] **Step 4: 运行新增来源页测试并确认失败**

Run: `python -m pytest tests\integration\test_pages.py -k new_source_page -q`
Expected: FAIL，因为当前 `/sources/new` 仍为浅色主题。

- [ ] **Step 5: 为任务详情页添加深色主题断言**

在 `test_job_detail_page_shows_progress_and_log_sections` 中增加断言：

```python
assert "theme-dark" in response.text
assert "page-header" in response.text
```

- [ ] **Step 6: 运行任务详情页测试并确认失败**

Run: `python -m pytest tests\integration\test_pages.py -k job_detail_page -q`
Expected: FAIL，因为当前 `/jobs/{id}` 仍为浅色主题。

- [ ] **Step 7: 为调度页添加深色主题断言**

在 `test_scheduler_page_shows_settings_panel` 中增加断言：

```python
assert "theme-dark" in response.text
```

- [ ] **Step 8: 运行调度页测试并确认失败**

Run: `python -m pytest tests\integration\test_pages.py -k scheduler_page -q`
Expected: FAIL，因为当前 `/scheduler` 仍为浅色主题。

- [ ] **Step 9: 新增报告页统一外壳测试**

增加一个新测试，验证 `/reports` 与 `/reports/{id}` 至少具备：

```python
assert "app-shell" in response.text
assert "theme-dark" in response.text
assert "panel" in response.text
```

- [ ] **Step 10: 运行报告页测试并确认失败**

Run: `python -m pytest tests\integration\test_pages.py -k reports_page -q`
Expected: FAIL，因为当前报告页还是裸 HTML。

- [ ] **Step 11: 检查点**

确认测试已经准确锁定“内页仍是浅色”和“报告页未接入统一壳”这两个现状问题。

### Task 2: 扩展共享主题以支持全站深色统一

**Files:**
- Modify: `app/ui/page_theme.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: 为深色业务页补充通用样式需求**

在测试未通过的前提下，梳理需要新增或调整的类：深色输入框、深色 checkbox 行、日志列表、报告预览 `pre`、深色空状态、深色次按钮、辅助文案对比度。

- [ ] **Step 2: 实现最小主题扩展**

在 `app/ui/page_theme.py` 中补充或调整样式，目标包括：

```python
# 继续保留 render_page/render_panel 等函数签名
# 调整 CSS 让 theme-dark 下的 panel、input、checkbox-row、metric-tile、empty-state、job-error、pre 可读
```

- [ ] **Step 3: 运行已失败的局部测试，确认仍然只因页面未切主题而失败**

Run: `python -m pytest tests\integration\test_pages.py -k "sources_page or new_source_page or job_detail_page or scheduler_page" -q`
Expected: 仍 FAIL，但失败点应集中在页面返回的 `theme-light` 或报告页裸 HTML，而不是样式类缺失。

- [ ] **Step 4: 检查点**

确认公共主题层已经具备支撑全站深色页的能力，再进入页面接入。

### Task 3: 统一来源管理、来源新增、任务详情、调度页到首页风格

**Files:**
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: 将 `/sources` 切换为深色主题**

把 `sources_page()` 的 `render_page(... body_class='theme-light')` 改为首页同一主题：

```python
return render_page(title=SOURCES_TITLE, content=content, body_class='theme-dark')
```

- [ ] **Step 2: 运行来源管理页测试并确认通过**

Run: `python -m pytest tests\integration\test_pages.py -k sources_page -q`
Expected: PASS。

- [ ] **Step 3: 将 `/sources/new` 切换为深色主题**

最小修改 `new_source_page()` 返回主题为 `theme-dark`。

- [ ] **Step 4: 运行新增来源页测试并确认通过**

Run: `python -m pytest tests\integration\test_pages.py -k new_source_page -q`
Expected: PASS。

- [ ] **Step 5: 将 `/jobs/{id}` 切换为深色主题**

最小修改 `job_detail_page()` 返回主题为 `theme-dark`，保留自动刷新脚本与现有结构。

- [ ] **Step 6: 运行任务详情页测试并确认通过**

Run: `python -m pytest tests\integration\test_pages.py -k job_detail_page -q`
Expected: PASS。

- [ ] **Step 7: 将 `/scheduler` 切换为深色主题**

最小修改 `scheduler_page()` 返回主题为 `theme-dark`。

- [ ] **Step 8: 运行调度页测试并确认通过**

Run: `python -m pytest tests\integration\test_pages.py -k scheduler_page -q`
Expected: PASS。

- [ ] **Step 9: 回归业务页现有局部测试**

Run: `python -m pytest tests\integration\test_pages.py -k "job_progress_partial or job_logs_partial or config_error or saving_dingtalk_settings" -q`
Expected: PASS，确认业务逻辑未因主题切换受影响。

- [ ] **Step 10: 检查点**

确认主要业务页已统一到首页风格，且原有业务行为不回归。

### Task 4: 将报告列表与报告详情迁移到统一页面壳

**Files:**
- Modify: `app/api/routes_reports.py`
- Modify: `app/ui/page_theme.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: 让报告路由复用共享 UI helper**

在 `app/api/routes_reports.py` 中引入：

```python
from app.ui.page_theme import render_page, render_page_header, render_panel
```

- [ ] **Step 2: 重写 `/reports` 页面为统一深色壳**

保持现有报告链接逻辑，仅将输出 HTML 改为共享结构，空状态也放进统一面板。

- [ ] **Step 3: 运行报告列表测试并确认通过**

Run: `python -m pytest tests\integration\test_pages.py -k reports_page -q`
Expected: PASS。

- [ ] **Step 4: 重写 `/reports/{id}` 页面为统一深色壳**

把导航按钮、下载入口和 Markdown 预览放进统一页头与面板，保留 `pre` 预览行为。

- [ ] **Step 5: 运行报告详情相关测试并确认通过**

Run: `python -m pytest tests\integration\test_reports.py -q`
Expected: PASS。

- [ ] **Step 6: 检查点**

确认报告页不再是裸 HTML，并与首页主题一致。

### Task 5: 全量验证统一主题与回归行为

**Files:**
- Modify: `tests/integration/test_pages.py`（如需微调断言文字）

- [ ] **Step 1: 运行页面集成测试**

Run: `python -m pytest tests\integration\test_pages.py -q`
Expected: PASS。

- [ ] **Step 2: 运行报告集成测试**

Run: `python -m pytest tests\integration\test_reports.py -q`
Expected: PASS。

- [ ] **Step 3: 如果页面测试依赖共享样式，检查首页回归**

Run: `python -m pytest tests\integration\test_pages.py -k "index_page or latest_job_summary" -q`
Expected: PASS。

- [ ] **Step 4: 记录非自动化检查点**

人工确认：

- 首页未退化
- `/sources`、`/sources/new`、`/jobs/{id}`、`/scheduler`、`/reports`、`/reports/{id}` 均为首页同一深色体系
- 深色背景下表单、日志、报告预览具备足够可读性

- [ ] **Step 5: 完成检查点**

准备进入最终验证与结果汇报。
