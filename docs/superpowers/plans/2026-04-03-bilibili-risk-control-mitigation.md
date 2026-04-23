# B站风控缓解与浏览器登录态持久化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 B站主页视频采集在命中 `-352/-412` 风控时继续走页面解析，同时提供一个网页入口打开真实浏览器登录并自动把最新登录态同步到 `app.env`。

**Architecture:** 采集链路从“API 优先且 API 风控即失败”调整为“页面优先容错”，即记录 WBI API 结果，但只有 API 成功时才直接使用；若 API 风控或返回异常，则继续解析已打开页面的 HTML。运维链路新增一个独立的浏览器登录服务，使用 Playwright 的持久化上下文打开真实浏览器，等待用户完成登录后保存 `storage_state`，并把提取出的 Cookie 严格规范化写入 `app.env`。

**Tech Stack:** FastAPI, Playwright, pytest, runtime `app.env`

---

| 文件 | 动作 | 责任 |
|---|---|---|
| `app/services/strategies/bilibili_profile_videos_recent.py` | Modify | API 风控时继续 fallback，优先复用持久化登录态 |
| `app/services/bilibili_auth_service.py` | Create | 浏览器登录、保存 storage state、导出 Cookie 到 `app.env` |
| `app/runtime_paths.py` | Modify | 增加 B站登录态存储路径 |
| `app/api/routes_pages.py` | Modify | `/scheduler` 新增“打开浏览器登录并同步”入口与结果提示 |
| `tests/unit/test_strategy_bilibili_profile_videos_recent.py` | Modify | 补充风控 fallback 与 storage state 使用测试 |
| `tests/unit/test_bilibili_auth_service.py` | Create | 覆盖浏览器登录服务的成功/超时/导出逻辑 |
| `tests/unit/test_runtime_paths.py` | Modify | 覆盖新增运行路径 |
| `tests/integration/test_pages.py` | Modify | 覆盖 `/scheduler` 新入口和成功/失败提示 |
| `docs/bilibili-cookie-运维说明.md` | Modify | 更新推荐操作路径，从“纯手贴 Cookie”改为“浏览器登录优先” |

### Task 1: B站 profile 风控 fallback

**Files:**
- Modify: `tests/unit/test_strategy_bilibili_profile_videos_recent.py`
- Modify: `app/services/strategies/bilibili_profile_videos_recent.py`

- [ ] **Step 1: 写失败测试，证明 API 返回 `-352` 时仍应继续解析 HTML**
- [ ] **Step 2: 运行聚焦测试，确认当前实现因直接抛错而失败**
- [ ] **Step 3: 最小实现，只在 API `code == 0` 时走 API 结果，其它情况记录日志并继续 HTML fallback**
- [ ] **Step 4: 为持久化 `storage_state` 优先加载补一条失败测试**
- [ ] **Step 5: 最小实现，在存在运行时 `storage_state` 文件时传给 Playwright context**
- [ ] **Step 6: 重新运行本文件测试，确认全部通过**

### Task 2: 浏览器登录并同步 `app.env`

**Files:**
- Create: `tests/unit/test_bilibili_auth_service.py`
- Modify: `tests/unit/test_runtime_paths.py`
- Modify: `tests/integration/test_pages.py`
- Modify: `app/runtime_paths.py`
- Create: `app/services/bilibili_auth_service.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: 写失败测试，证明运行路径需要包含 B站登录态目录和 storage state 文件**
- [ ] **Step 2: 写失败测试，证明浏览器登录成功后会把 Cookie 写入 `app.env`**
- [ ] **Step 3: 写失败测试，证明 `/scheduler` 页面存在“打开浏览器登录并同步”入口与成功提示**
- [ ] **Step 4: 最小实现运行路径与登录服务**
- [ ] **Step 5: 最小实现 `/scheduler/bilibili/browser-login` 路由与页面提示**
- [ ] **Step 6: 运行聚焦单元测试和集成测试，确认通过**

### Task 3: 文档与回归

**Files:**
- Modify: `docs/bilibili-cookie-运维说明.md`

- [ ] **Step 1: 更新运维说明，明确“浏览器登录同步”为主流程，手工粘贴 Cookie 为备用流程**
- [ ] **Step 2: 运行本次相关测试集合**
- [ ] **Step 3: 记录仍未解决的残余风险，只保留真实存在的问题**
