# 最近一周热点表格页 Implementation Plan

状态：已完成（2026-04-26 已落地并回归通过）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有系统内新增一个固定周榜页，展示最近 7 天采集到的热点内容，并按“序号、标题链接、封面、点赞、播放、评论、发布时间”输出表格。

**Architecture:** 新增一个轻量查询服务负责最近一周窗口过滤和排序；在现有报告路由中增加 `/weekly` 页面；在主题样式中补表格与封面缩略图样式；首页补一个快捷入口。页面继续使用服务端渲染，不引入新前端层。

**Tech Stack:** FastAPI, SQLAlchemy ORM, pytest, existing page theme renderer

---

## 文件结构

| 路径 | 责任 |
|---|---|
| `app/services/weekly_hot_service.py` | 最近一周热点查询与排序 |
| `app/api/routes_reports.py` | `GET /weekly` 页面 |
| `app/api/routes_pages.py` | 首页增加周榜页入口 |
| `app/ui/page_theme.py` | 表格页样式与封面缩略图样式 |
| `tests/unit/test_weekly_hot_service.py` | 服务级过滤与排序测试 |
| `tests/integration/test_reports.py` | 周榜页访问与渲染测试 |

### Task 1: 先写周榜服务失败测试

**Files:**
- Create: `tests/unit/test_weekly_hot_service.py`
- Create: `app/services/weekly_hot_service.py`

- [x] **Step 1: 写“最近 7 天过滤 + 发布时间倒序”的失败测试**
- [x] **Step 2: 运行 `pytest tests/unit/test_weekly_hot_service.py -v`，确认先失败**
- [x] **Step 3: 实现最小 `WeeklyHotService` 让测试转绿**
- [x] **Step 4: 重新运行同一测试，确认通过**

### Task 2: 写周榜页面失败测试

**Files:**
- Modify: `tests/integration/test_reports.py`
- Modify: `app/api/routes_reports.py`
- Modify: `app/ui/page_theme.py`

- [x] **Step 1: 补 `/weekly` 页面集成失败测试**
- [x] **Step 2: 运行 `pytest tests/integration/test_reports.py -v`，确认新断言失败**
- [x] **Step 3: 实现页面路由和基础表格 HTML**
- [x] **Step 4: 重新运行页面测试，确认通过**

### Task 3: 接入首页入口和样式补齐

**Files:**
- Modify: `app/api/routes_pages.py`
- Modify: `app/ui/page_theme.py`

- [x] **Step 1: 补首页入口相关断言**
- [x] **Step 2: 实现快捷入口和表格/封面样式**
- [x] **Step 3: 运行相关页面测试确认不回归**

### Task 4: 完整验证

**Files:**
- None

- [x] **Step 1: 运行 `pytest tests/unit/test_weekly_hot_service.py tests/integration/test_reports.py tests/integration/test_pages.py -v`**
- [x] **Step 2: 如有失败，修正后重跑**
- [x] **Step 3: 记录最终验证结果和已知边界**

## 最终结果

| 项目 | 结果 |
| --- | --- |
| 页面路由 | 已提供 `/weekly` 固定入口 |
| 首页入口 | 已提供首页快捷卡片跳转 |
| 渲染字段 | 已覆盖序号、标题、封面、点赞、播放、评论、发布时间 |
| 验证结果 | 已纳入后续更大范围回归，相关测试通过 |
| 已知边界 | 第一版仍为服务端渲染，无筛选、分页和导出能力 |
