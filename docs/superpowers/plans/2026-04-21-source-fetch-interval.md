# Source Fetch Interval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为来源执行器增加可配置的全局抓取间隔与 B站专用间隔，并在调度页提供保存入口。

**Architecture:** 保持现有串行抓取模型不变，只在 `JobRunner` 的来源循环前增加等待决策。配置统一从 `app.env` 读取，并复用 `/scheduler` 页面现有的运维设置入口。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, runtime `app.env`

---

### Task 1: 配置读写

**Files:**
- Modify: `tests/unit/test_config.py`
- Modify: `tests/unit/test_app_env_service.py`
- Modify: `app/config.py`
- Modify: `app/services/app_env_service.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: 调度页入口

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 3: 执行器等待逻辑

**Files:**
- Modify: `tests/unit/test_runner.py`
- Modify: `app/workers/runner.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 4: 回归验证

**Files:**
- Modify: `tests/unit/test_report_service.py`

- [ ] **Step 1: Run focused regression tests**
- [ ] **Step 2: Run related suites**
- [ ] **Step 3: Confirm outputs and finish**
