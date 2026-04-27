# Auth State Status Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增独立账号态状态页 `/auth-state` 和系统接口 `/system/auth-state`，统一暴露账号态快照。

**Architecture:** 先从单用户状态聚合起步，再向多账号结构扩展。系统接口与页面都消费同一份快照，同时把页面入口挂进 `desktop-manifest.navigation`。

**Tech Stack:** Python 3.11, FastAPI, pytest

---

## 当前执行状态（2026-04-26）

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| Task 1 | 已完成 | `GET /system/auth-state`、`/auth-state`、desktop manifest 导航的测试已补齐 |
| Task 2 | 已完成 | 已新增 `app/services/auth_state_status_service.py`，统一聚合 Cookie / storage state / user-data 目录状态 |
| Task 3 | 已完成 | 已接入系统 API、HTML 页面和 desktop manifest 导航 |
| Task 4 | 已完成 | README、API 文档、roadmap 已同步 |
| 后续扩展 | 已覆盖 | 原计划按单用户起步；当前仓库已进一步扩展为 B站多账号快照结构 |

---

### Task 1: 先锁定账号态快照契约

**Files:**
- Modify: `tests/integration/test_system_api.py`
- Modify: `tests/integration/test_pages.py`
- Create: `tests/unit/test_auth_state_status_service.py`

- [x] **Step 1: Write failing tests for `GET /system/auth-state`, `/auth-state`, and desktop manifest navigation**
- [x] **Step 2: Run targeted pytest and verify failures are due to missing service/route/page**
- [x] **Step 3: Keep fixtures focused on single-user Bilibili state only**
- [x] **Step 4: Re-run the same tests after implementation and verify they pass**

### Task 2: 新增账号态状态聚合服务

**Files:**
- Create: `app/services/auth_state_status_service.py`
- Test: `tests/unit/test_auth_state_status_service.py`

- [x] **Step 1: Add a minimal service that reads Cookie config, storage state file, and user-data directory**
- [x] **Step 2: Implement `ok` / `warning` / `missing` / `error` transitions exactly as specified**
- [x] **Step 3: Return a snapshot structure suitable for both API and page rendering**

### Task 3: 接入系统 API 与页面

**Files:**
- Modify: `app/api/routes_system.py`
- Modify: `app/api/routes_pages.py`
- Modify: `app/schemas/system_manifest.py` if navigation typing needs update

- [x] **Step 1: Add `GET /system/auth-state` using the shared service**
- [x] **Step 2: Add `/auth-state` page using the same snapshot**
- [x] **Step 3: Append `/auth-state` to desktop manifest navigation**
- [x] **Step 4: Keep `/scheduler` login save and browser sync behavior unchanged**

### Task 4: 文档与验证

**Files:**
- Modify: `README.md`
- Modify: `docs/specs/api-reference.md`
- Modify: roadmap/doc status files if needed

- [x] **Step 1: Document the new API/page entry**
- [x] **Step 2: Run targeted pytest verification**
- [x] **Step 3: Run broader regression set if page/system contract changed**
- [x] **Step 4: Run `git diff --check`**
