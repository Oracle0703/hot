# Offline Release Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一个适用于空白 Windows 环境的尽量离线即开即用发布包，包含主程序、内置浏览器、依赖安装脚本、默认配置模板和最终 zip 文件。

**Architecture:** 复用现有 PyInstaller 与 release 目录流程，在其外层增加一个离线发布编排脚本。该脚本负责准备 prerequisites、写入安装/启动说明、复制 Playwright 浏览器、生成压缩包，并尽量减少同事机器上的联网依赖。

**Tech Stack:** PowerShell、PyInstaller、Playwright、Windows 批处理脚本

---

### Task 1: 补齐离线发布编排脚本

**Files:**
- Create: `scripts/build_offline_release.ps1`
- Modify: `scripts/prepare_release.ps1`

- [ ] 写离线发布脚本，串联 build、prepare、prerequisites、zip
- [ ] 让脚本默认复用本地 `playwright-browsers`
- [ ] 支持将 VC++ 运行库放进 `prerequisites`
- [ ] 生成最终 `zip`

### Task 2: 补齐同事端安装入口

**Files:**
- Modify: `scripts/prepare_release.ps1`
- Modify: `README-运营版.txt`

- [ ] 在发布目录生成 `安装依赖.bat`
- [ ] 在 `app.env` 模板中补齐钉钉与 X 配置说明
- [ ] 在 README 中补齐“先装依赖再启动”的说明

### Task 3: 实际构建并验证发布物

**Files:**
- Output: `release/...`
- Output: `dist/...`

- [ ] 运行构建脚本产出 exe
- [ ] 运行离线发布脚本产出 release 与 zip
- [ ] 检查发布目录结构
- [ ] 用启动器做一次本地 dry-run / 结构验证
