# Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the FastAPI server-rendered pages into a modern data-hub style UI with a dark dashboard homepage and light professional inner pages without changing routes or business behavior.

**Architecture:** Introduce a small shared page-rendering helper for theme tokens, layout shell, cards, buttons, badges, and panel wrappers, then migrate `routes_pages.py` page-by-page onto that shell. Keep all existing endpoints and interaction logic intact while updating `tests/integration/test_pages.py` to assert the new shared structure and preserve critical page behavior.

**Tech Stack:** FastAPI, server-rendered HTML strings, Python helper functions, pytest integration tests

---

## File Structure

| Path | Action | Responsibility |
| --- | --- | --- |
| `app/ui/__init__.py` | Create | UI helper package marker |
| `app/ui/page_theme.py` | Create | Shared CSS tokens, page shell, reusable UI fragments |
| `app/api/routes_pages.py` | Modify | Migrate homepage, sources, new-source, job detail, scheduler pages to shared shell |
| `tests/integration/test_pages.py` | Modify | Add failing assertions for new shell markers and preserve behavior regression coverage |
| `docs/superpowers/specs/2026-03-26-visual-refresh-design.md` | Keep | Approved design reference |
| `docs/superpowers/plans/2026-03-26-visual-refresh.md` | Create | This execution plan |

## Execution Notes

- The current workspace is **not a git repository**, so commit steps are documented as checkpoints rather than executable `git commit` commands.
- Follow TDD per page slice: add/adjust a failing assertion, run the focused test, implement the minimum markup/style change, then rerun the focused test.
- Preserve all route paths, form field names, fetch URLs, and auto-refresh JavaScript behavior.

### Task 1: Create Shared Page Shell And Theme Helpers

**Files:**
- Create: `app/ui/__init__.py`
- Create: `app/ui/page_theme.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing shell test assertions**

Add or extend a focused integration test so the homepage expects stable shell markers, for example:

```python
response = client.get("/")
assert "app-shell" in response.text
assert "page-hero" in response.text
assert "stat-card" in response.text
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python -m pytest tests\integration\test_pages.py -k dashboard_actions -q`
Expected: FAIL because the current homepage has no shared shell classes.

- [ ] **Step 3: Create the UI helper package marker**

Create `app/ui/__init__.py` with a minimal export surface:

```python
from app.ui.page_theme import render_page

__all__ = ["render_page"]
```

- [ ] **Step 4: Create the shared theme helper**

Create `app/ui/page_theme.py` with small focused helpers like:

```python
def render_page(*, title: str, body_class: str, content: str, page_class: str = "") -> str:
    ...

def render_badge(label: str, tone: str = "neutral") -> str:
    ...

def render_panel(title: str, content: str, extra_class: str = "") -> str:
    ...
```

Include one embedded CSS string that defines the visual system (`app-shell`, `page-hero`, `panel`, `stat-card`, `status-badge`, buttons, form controls, responsive rules).

- [ ] **Step 5: Run the focused test to verify it passes**

Run: `python -m pytest tests\integration\test_pages.py -k dashboard_actions -q`
Expected: PASS.

- [ ] **Step 6: Checkpoint**

Record that the shared shell exists and can be reused by all pages.

### Task 2: Refresh The Homepage Dashboard

**Files:**
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write a failing homepage layout assertion**

Extend homepage coverage to expect the dashboard-specific sections, for example:

```python
assert "热点信号总览" in response.text
assert "recent-jobs" in response.text
assert "quick-actions" in response.text
```

- [ ] **Step 2: Run the focused homepage tests to verify failure**

Run: `python -m pytest tests\integration\test_pages.py -k "index_page" -q`
Expected: FAIL because the old homepage is plain text.

- [ ] **Step 3: Implement the homepage on the shared shell**

Update `index_page()` to:

```python
hero = """
<section class='page-hero dashboard-hero'>...</section>
"""
metrics = """
<section class='stats-grid'>...</section>
"""
```

Render:
- dark hero area
- 3-4 stat cards
- recent jobs panel
- quick actions / system links panel

Keep the existing `/jobs/run`, `/sources`, `/reports`, `/scheduler` links intact.

- [ ] **Step 4: Run the focused homepage tests to verify pass**

Run: `python -m pytest tests\integration\test_pages.py -k "index_page" -q`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Confirm the homepage now reflects the approved dark “signal center” direction.

### Task 3: Refresh Sources List And New Source Form

**Files:**
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write failing assertions for source management layout**

Add expectations for structured source cards and the new form shell, for example:

```python
assert "source-grid" in response.text
assert "resource-card" in response.text
assert "form-panel" in response.text
```

- [ ] **Step 2: Run the focused sources page tests to verify failure**

Run: `python -m pytest tests\integration\test_pages.py -k "sources_page or new_source_page" -q`
Expected: FAIL because both pages still use unstyled raw markup.

- [ ] **Step 3: Implement the refreshed `/sources` page**

Update `sources_page()` to render:
- page header with title and action button
- empty state panel when no sources exist
- card/list entries showing name, site, fetch mode, entry URL, and action link

Suggested fragment:

```python
cards = "".join(render_source_card(source) for source in sources)
content = f"<section class='source-grid'>{cards}</section>"
```

- [ ] **Step 4: Implement the refreshed `/sources/new` page**

Update `new_source_page()` to render:
- header with helper text
- form wrapped in a panel/card
- consistent labeled inputs and primary submit button

Do **not** change field names: `entry_url`, `search_keyword`, `max_items`.

- [ ] **Step 5: Run the focused sources tests to verify pass**

Run: `python -m pytest tests\integration\test_pages.py -k "sources_page or new_source_page" -q`
Expected: PASS.

- [ ] **Step 6: Checkpoint**

Confirm list readability and form clarity improved without altering simplified source creation behavior.

### Task 4: Refresh Job Detail And Scheduler Pages

**Files:**
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write failing assertions for job and scheduler layout markers**

Add or extend tests to expect structure like:

```python
assert "job-detail-layout" in response.text
assert "log-panel" in response.text
assert "scheduler-settings-panel" in response.text
```

- [ ] **Step 2: Run the focused job/scheduler tests to verify failure**

Run: `python -m pytest tests\integration\test_pages.py -k "job_detail_page or scheduler_page or progress_partial or logs_partial" -q`
Expected: FAIL because current pages are still raw sections.

- [ ] **Step 3: Implement the refreshed job detail page**

Update `job_detail_page()` plus shared partial renderers to use consistent panels and badges:

```python
progress = render_panel("任务进度", render_progress_panel(...), extra_class="progress-panel")
logs = render_panel("任务日志", render_log_list(...), extra_class="log-panel")
```

Preserve:
- `progress-host`
- `job-log-host`
- fetch endpoints
- `setInterval(refreshJobDetail, 2000)`

- [ ] **Step 4: Implement the refreshed scheduler page**

Update `scheduler_page()` to use:
- status summary card
- settings panel
- clearer form grouping for enable toggle and daily time

- [ ] **Step 5: Run the focused job/scheduler tests to verify pass**

Run: `python -m pytest tests\integration\test_pages.py -k "job_detail_page or scheduler_page or progress_partial or logs_partial" -q`
Expected: PASS.

- [ ] **Step 6: Checkpoint**

Confirm monitoring and settings pages now match the shared professional backend language.

### Task 5: Full Regression Verification And Cleanup

**Files:**
- Modify: `app/api/routes_pages.py` (only if cleanup is needed)
- Modify: `tests/integration/test_pages.py` (only if assertion wording needs cleanup)

- [ ] **Step 1: Run the full page integration suite**

Run: `python -m pytest tests\integration\test_pages.py -q`
Expected: PASS with all page routes still covered.

- [ ] **Step 2: Run the source API regression suite**

Run: `python -m pytest tests\integration\test_sources_api.py -q`
Expected: PASS, proving the page/UI refresh did not break source creation behavior.

- [ ] **Step 3: Manually smoke-test the UI**

Run the app and inspect:
- `/`
- `/sources`
- `/sources/new`
- `/scheduler`
- one `/jobs/{id}` page after triggering a job

Expected: homepage is dark and high-impact; inner pages are light, readable, and visually consistent.

- [ ] **Step 4: Final cleanup pass**

Keep only the shared helpers actually used. Remove duplicated inline markup patterns if the new helper covers them.

- [ ] **Step 5: Final checkpoint**

Document verification results in the handoff response. Since there is no git repository here, explicitly state that commit steps were skipped.