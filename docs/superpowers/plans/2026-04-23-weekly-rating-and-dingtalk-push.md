# 周榜人工评分与批量钉钉推送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/weekly` 页面增加推荐评分、人工评分、推送状态，并支持“保存评分”和“批量推送达标项到钉钉”。

**Architecture:** 将评分与推送状态直接挂在 `CollectedItem`；新增评分规则与周榜批量推送 service；周榜页通过表单保存人工评分，再通过单独按钮触发合并消息推送；阈值由配置控制。

**Tech Stack:** FastAPI, SQLAlchemy ORM, pytest, existing DingTalk webhook flow

---

## 文件结构

| 路径 | 责任 |
|---|---|
| `app/models/item.py` | 增加评分与推送字段 |
| `app/db.py` | SQLite 补列兼容 |
| `app/config.py` | 推送阈值配置 |
| `app/services/weekly_rating_service.py` | 推荐评分、等级比较、保存评分 |
| `app/services/weekly_dingtalk_push_service.py` | 批量筛选并合成 1 条钉钉消息 |
| `app/api/routes_reports.py` | 周榜页评分列、保存、批量推送 |
| `app/ui/page_theme.py` | 评分列与状态样式 |
| `tests/unit/test_weekly_rating_service.py` | 推荐评分和等级比较 |
| `tests/unit/test_weekly_dingtalk_push_service.py` | 达标筛选、去重推送 |
| `tests/integration/test_reports.py` | 页面保存评分与批量推送 |

## 实施顺序

| 顺序 | 内容 |
|---|---|
| 1 | 先补字段与评分 service 失败测试 |
| 2 | 实现推荐评分和等级阈值比较 |
| 3 | 补 `/weekly` 页面评分列与保存表单 |
| 4 | 实现批量钉钉推送 service 和页面按钮 |
| 5 | 跑周榜相关单测与集成测试 |
