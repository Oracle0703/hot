# 技术架构说明

本文档用于沉淀项目当前架构边界，帮助后续维护者理解系统如何启动、采集、调度、生成报告和打包交付。

## 架构目标

| 目标 | 说明 |
| --- | --- |
| 本地优先 | 默认在固定电脑本地运行，降低部署和运维复杂度 |
| 可打包交付 | 通过 PyInstaller 生成 `onedir` 目录包，适合发给运营同学使用 |
| 配置可持久化 | 运行配置落在 `data/app.env`，页面和脚本可复用同一份配置 |
| 数据可迁移 | 默认 SQLite，保留切换 MySQL 的能力 |
| 采集可扩展 | 通用 CSS 采集器与专用策略并存，便于逐步增加站点能力 |
| 报告可复用 | 采集结果统一进入任务与报告链路，输出 Markdown 和 DOCX |

## 分层结构

| 层级 | 主要路径 | 职责 |
| --- | --- | --- |
| 启动层 | `launcher.py`、`scripts/run.ps1`、`scripts/status.ps1`、`scripts/stop.ps1` | 准备运行环境、启动服务、打开浏览器、记录启动日志，并通过 dry-run / probe / stop JSON 输出向桌面壳和运维脚本暴露稳定的本地控制面 |
| 应用层 | `app/main.py` | 组装 FastAPI 应用、生命周期、数据库初始化和调度器 |
| 路由层 | `app/api/` | 提供页面路由和 API 路由 |
| 服务层 | `app/services/` | 承载业务流程，包括来源、任务、报告、调度、配置、通知 |
| 采集层 | `app/collectors/`、`app/services/strategies/` | 执行 HTTP、Playwright 或站点专用采集 |
| 持久化层 | `app/models/`、`app/db.py` | SQLAlchemy 模型和数据库连接 |
| 运行路径层 | `app/runtime_paths.py` | 统一源码运行与打包运行的路径规则 |
| 发布脚本层 | `scripts/build_*.ps1`、`scripts/prepare_*.ps1` | 打包、组装发布目录和生成升级包 |

## 核心运行流程

| 阶段 | 数据流 |
| --- | --- |
| 启动 | `launcher.py` 或 `scripts/run.ps1` 读取 `data/app.env`，再启动 FastAPI |
| 初始化 | `app/main.py` 创建数据库表、装配路由、启动后台调度线程 |
| 配置来源 | 用户通过 `/sources` 页面或 API 写入 `sources` 表 |
| 创建任务 | 首页手动触发或调度器自动创建 `jobs` 记录 |
| 执行采集 | `JobDispatcher` 调用 `JobRunner`，再由 `SourceExecutionService` 分发到采集策略 |
| 写入结果 | 采集到的条目写入数据库并记录任务日志 |
| 生成报告 | `ReportService` 输出 Markdown/DOCX，并登记报告记录 |
| 查看结果 | 页面通过任务详情、报告列表和下载接口查看结果 |

## 采集架构

| 类型 | 入口 | 适用场景 |
| --- | --- | --- |
| 通用 CSS 采集 | `app/collectors/http_collector.py`、`generic_css_parser.py` | 普通网页列表页 |
| Playwright 采集 | `app/collectors/playwright_collector.py` | 需要浏览器渲染的网页 |
| 专用策略 | `app/services/strategies/` | B站、YouTube、X 等有特殊规则的网站 |
| 策略注册 | `app/collectors/registry.py` 与服务层策略分流 | 将来源配置映射到具体采集实现 |

长期方向是把 `app/services/strategies/` 沉淀为更明确的插件式接口：统一输入、统一输出、统一错误类型、统一测试夹具。

## 配置与运行数据

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 配置模板 | `.env.example` | 可提交的空值示例 |
| 本地运行配置 | `data/app.env` | 不提交，可能包含 Cookie、Token、Webhook |
| SQLite 数据库 | `data/hot_topics.db` | 不提交，属于运行数据 |
| 浏览器登录态 | `data/bilibili-user-data/`、`data/bilibili-storage-state.json` | 不提交，属于敏感运行状态 |
| 日志 | `logs/` | 不提交 |
| 报告 | `outputs/reports/` | 不提交，可按需人工分发 |
| 发布产物 | `build/`、`dist/`、`release/` | 不提交，可通过脚本再生成 |

## 发布架构

| 脚本 | 职责 |
| --- | --- |
| `scripts/build_package.ps1` | 使用 PyInstaller 生成 `dist/HotCollectorLauncher/` |
| `scripts/prepare_release.ps1` | 从 `dist/` 组装固定发布目录 |
| `scripts/build_offline_release.ps1` | 一键构建完整离线包并压缩 |
| `scripts/prepare_upgrade_release.ps1` | 组装仅覆盖程序文件的升级包目录 |
| `scripts/build_upgrade_release.ps1` | 一键构建升级包并压缩 |

## 当前架构边界

| 边界 | 当前选择 |
| --- | --- |
| Web UI | 服务端 HTML + 轻量 JS，不做前后端分离 |
| 调度 | 应用内后台线程，不引入外部任务队列 |
| 存储 | 默认 SQLite，可配置 MySQL |
| 部署 | 固定电脑本地运行，暂不按 SaaS 多租户设计 |
| 打包 | PyInstaller `onedir`，不追求单文件 exe |
