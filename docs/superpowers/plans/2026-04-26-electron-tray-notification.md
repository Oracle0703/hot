# Electron Tray Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前 Electron 最小壳体增加托盘常驻与系统通知，基于现有 `probe`、`/system/auth-state`、`/system/health/extended` 提供本地运行体验增强。

**Architecture:** 保持 Python 内核不变，所有托盘与通知逻辑都放在 Electron 主进程中。主进程定时轮询已有状态源，维护一个归一化本地状态，并用状态迁移规则触发去重通知。

**Tech Stack:** Electron、Node.js、PowerShell、pytest

---

## 当前执行状态（2026-04-26）

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| Task 1 | 已完成 | 已新增 `tests/integration/test_scripts.py` 的桌面壳脚本断言与 `desktop-shell/electron/shell-state.test.js` |
| Task 2 | 已完成 | 已抽出 `desktop-shell/electron/shell-state.js`，用于归一化状态与通知去重 |
| Task 3 | 已完成 | Electron 主进程已接入托盘、账号态快捷入口、启动/停止/刷新、关闭隐藏到托盘、系统通知 |
| Task 4 | 已完成 | README、`docs/desktop-shell-integration.md`、roadmap 状态与相关测试验证已同步 |
| 当前契约 | 已稳定 | 桌面壳仍只消费既有 Python HTTP / launcher 控制面，不新增私有 IPC |

---

### Task 1: 先锁定托盘与通知契约

**Files:**
- Modify: `tests/integration/test_scripts.py`
- Create: `tests/unit/test_desktop_shell_state.js` or equivalent Node-side test target if repo chooses shell-based verification

- [x] **Step 1: Write failing tests for tray-enabled shell artifacts or state helper outputs**
- [x] **Step 2: Run the focused tests and verify they fail because tray/notification helpers do not exist yet**
- [x] **Step 3: Keep the first assertions focused on state transitions and release integrity**
- [x] **Step 4: Re-run the same tests after implementation and verify they pass**

### Task 2: 抽出主进程状态轮询与通知去重逻辑

**Files:**
- Modify: `desktop-shell/electron/main.js`
- Optional Create: `desktop-shell/electron/shell-state.js`

- [x] **Step 1: Extract probe/auth/health polling into a small, testable helper**
- [x] **Step 2: Add a normalized shell state model and transition comparison**
- [x] **Step 3: Implement notification de-duplication based on transition keys**
- [x] **Step 4: Keep all logic local to Electron and do not modify Python runtime contracts**

### Task 3: 接入 Tray 与 Notification

**Files:**
- Modify: `desktop-shell/electron/main.js`
- Create: `desktop-shell/electron/assets/tray.ico`

- [x] **Step 1: Create Tray instance and tooltip text from normalized shell state**
- [x] **Step 2: Add tray menu items for open UI, open auth-state, start, stop, refresh, quit**
- [x] **Step 3: Make window close hide to tray instead of quitting**
- [x] **Step 4: Add notifications for service-started, auth-warning/error, health-error, and recovered**

### Task 4: 文档与验证

**Files:**
- Modify: `README.md`
- Modify: `docs/desktop-shell-integration.md`
- Modify: roadmap/doc status files if needed

- [x] **Step 1: Document tray behavior, close-to-tray behavior, and notification triggers**
- [x] **Step 2: Run focused Electron shell verification**
- [x] **Step 3: Run related Python regression around `desktop-manifest`, `auth-state`, and release scripts**
- [x] **Step 4: Run `git diff --check`**
