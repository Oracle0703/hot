# Electron Minimal Shell Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有 Python 发布包增加最小 Electron 桌面壳，并将其自动打进 release / 离线包 / 升级包。

**Architecture:** 保持 Python `HotCollectorLauncher.exe` 作为服务内核，Electron 仅负责桌面窗口与本地拉起。新增一个桌面壳构建脚本，把 Electron runtime 与 app 文件组装到独立目录，再由现有发布脚本复制进 release。

**Tech Stack:** PowerShell、Electron、Node.js、pytest

---

## 当前执行状态（2026-04-26）

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| Task 1 | 已完成 | 已补桌面壳发布契约测试，覆盖 `desktop-shell` 目录复制、`打开桌面版.bat` 与离线/升级包组装 |
| Task 2 | 已完成 | 已新增 `desktop-shell/electron/` 最小壳体与 `scripts/build_desktop_shell.ps1` |
| Task 3 | 已完成 | `prepare_release.ps1`、`prepare_upgrade_release.ps1`、`build_offline_release.ps1`、`build_upgrade_release.ps1` 已接入桌面壳构建与复制 |
| Task 4 | 已完成 | README、release 文档、桌面壳接入说明已同步 |
| 当前边界 | 已变更 | 原计划中的“避免 tray / notification scope creep”只适用于最小壳体阶段；当前仓库已在后续计划中继续补上托盘与通知 |

---

### Task 1: 先锁定发布产物契约

**Files:**
- Modify: `tests/integration/test_scripts.py`
- Test: `tests/integration/test_scripts.py`

- [x] **Step 1: Write the failing test**
- [x] **Step 2: Run `pytest tests/integration/test_scripts.py -k "desktop_shell or build_offline_release or build_upgrade_release" -v` and verify it fails for missing desktop shell release outputs**
- [x] **Step 3: Keep assertions focused on `desktop-shell` directory copy and `打开桌面版.bat` wrapper generation**
- [x] **Step 4: Re-run the same tests after implementation and verify they pass**

### Task 2: 组装最小 Electron 壳体

**Files:**
- Create: `desktop-shell/electron/package.json`
- Create: `desktop-shell/electron/main.js`
- Create: `scripts/build_desktop_shell.ps1`

- [x] **Step 1: Add the smallest Electron app that can probe/start the local launcher and load `desktop-manifest`**
- [x] **Step 2: Write a PowerShell build script that assembles a distributable desktop-shell runtime directory**
- [x] **Step 3: Keep the runtime self-contained so release does not require a separate system Electron install**
- [x] **Step 4: Avoid tray, notification, or installer scope creep**

### Task 3: 接入现有 release 链路

**Files:**
- Modify: `scripts/prepare_release.ps1`
- Modify: `scripts/prepare_upgrade_release.ps1`
- Modify: `scripts/build_offline_release.ps1`
- Modify: `scripts/build_upgrade_release.ps1`

- [x] **Step 1: Add parameters/defaults for desktop shell dist location**
- [x] **Step 2: Copy desktop-shell artifacts into release and upgrade package directories**
- [x] **Step 3: Generate `打开桌面版.bat` in release roots**
- [x] **Step 4: Ensure offline/upgrade build scripts invoke `build_desktop_shell.ps1` before assembly**

### Task 4: 文档与验证

**Files:**
- Modify: `README.md`
- Modify: `docs/release.md`
- Modify: `docs/desktop-shell-integration.md`

- [x] **Step 1: Update release structure and usage docs for Electron desktop shell**
- [x] **Step 2: Run targeted pytest verification**
- [x] **Step 3: Run `git diff --check`**
