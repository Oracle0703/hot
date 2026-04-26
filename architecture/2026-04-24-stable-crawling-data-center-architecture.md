# 稳定采集框架与数据处理中心架构方案

| 项目 | 内容 |
| --- | --- |
| 日期 | 2026-04-24 |
| 状态 | Draft v1 |
| 目标读者 | 当前维护者、后续协作者、未来接手者 |
| 文档定位 | 当前系统从单机采集工具升级为稳定采集框架、数据处理中心和订阅推送中心的总设计说明 |

## 1. 背景与目标

当前项目已经具备基础采集、浏览器抓取、登录态复用和本地分发能力，但整体仍偏向单机可用的采集工具。随着后续使用场景从单人扩展为多人、多业务线、多来源协同，系统目标需要升级为一个稳定的内部信息采集与分发平台。

| 目标 | 说明 |
| --- | --- |
| 稳定采集 | 面向公开页、登录页、强 JS / 风控页建立分层抓取能力 |
| 数据处理 | 对采集结果进行清洗、归一化、去重、分类、打标签和评分 |
| 信息共享 | 让人事、市场、运营等角色共享同一批可复用内容 |
| 主动分发 | 通过订阅规则将内容主动推送给对应角色，而不是只提供查询页 |
| 可长期演进 | 保持 Python 内核稳定，当前先按单用户运行，后续再按需扩展 Web 或桌面壳 |

## 2. 当前问题

当前项目的主要问题不是能不能抓，而是能不能长期稳定扩展。

| 问题 | 说明 |
| --- | --- |
| 采集能力偏工具化 | 还没有形成统一的采集治理框架 |
| 登录态管理分散 | Cookie、storage state、浏览器目录治理还不够统一 |
| 多人使用边界不清 | 后续多人共用来源和账号时容易相互影响 |
| 调度治理不足 | 限速、熔断、失败分类、恢复策略需要系统化 |
| 数据处理中心尚未建立 | 采集结果还未沉淀为统一内容资产 |
| 文档混乱 | 架构设计、实施计划、使用说明混在一起，难以持续维护 |

## 3. 总体架构

系统总体分为七层。

| 层 | 核心职责 |
| --- | --- |
| 接入层 | Web 管理台，后续可选桌面壳 |
| API 层 | 对外提供配置、任务、内容、订阅、投递接口 |
| 采集层 | 来源注册、执行引擎、站点策略 |
| 治理层 | 调度、重试、限速、熔断、登录态管理 |
| 处理层 | 清洗、去重、分类、标签、评分 |
| 分发层 | 订阅匹配、推送分发、投递记录 |
| 存储层 | 原始结果、内容对象、任务、账号态、订阅、投递日志 |

系统核心链路如下：

```text
Source
  -> Collector Engine
  -> RawItem
  -> Normalizer
  -> Deduplicator
  -> Enricher / Scoring
  -> ContentItem
  -> Subscription Matcher
  -> Push Dispatcher
  -> Delivery Record
```

### 3.1 当前仓库已落地映射

| 设计模块 | 当前实现 | 状态 |
| --- | --- | --- |
| 单用户登录态治理 | `app/services/auth_state_service.py` + `app/runtime_paths.py` | 已落地 |
| 失败分类与熔断 | `app/services/failure_classifier.py` + `app/services/circuit_breaker_service.py` + `app/workers/runner.py` | 已落地 |
| 内容流水线 | `app/services/content_normalizer_service.py` + `app/services/content_pipeline_service.py` | 已落地 |
| 订阅分发 | `app/services/subscription_matcher_service.py` + `app/services/content_dispatch_service.py` | 已落地 |
| 内容 API / 页面入口 | `/api/content` + `/content-center` | 已落地 |
| 订阅 API / 页面入口 | `/api/subscriptions` + `/subscriptions` | 已落地 |

### 3.2 当前迁移链

| Revision | 责任 |
| --- | --- |
| `0001_baseline` | 基础业务表 |
| `0002_retry_policy` | 重试策略相关结构 |
| `0004_content_center_models` | `raw_items`、`content_items` |
| `0005_subscriptions_and_delivery_records` | `subscriptions`、`delivery_records` |

## 4. 稳定采集框架设计

采集框架不采用单一路径，而是按来源特性自动选择最轻、最稳的执行方式。

| 来源类型 | 推荐路径 | 原则 |
| --- | --- | --- |
| 公开页 | `API -> HTTP HTML` | 能不用浏览器就不用 |
| 登录页 | `HTTP/API + 单用户登录态`，必要时 `Playwright` | 优先复用登录态 |
| 强 JS / 风控页 | `Playwright + storage state + 风控治理` | 以稳定性和可恢复性为主 |

采集层的关键模块如下。

| 模块 | 职责 |
| --- | --- |
| `Source Registry` | 管理来源定义、策略标识、绑定关系 |
| `Collector Engine` | 根据来源和能力生成执行计划 |
| `Site Strategy` | 处理各站点自己的取数、解析、异常识别 |
| `Fetch Result` | 标准化返回原始抓取结果 |

## 5. 登录态与账号体系

当前阶段先按单用户运行，不立即建设多账号体系。登录态仍需要被系统化管理，但优先目标是把单用户本地运行做稳，而不是立刻支持多人、多账号。

当前阶段建议如下：

| 项目 | 处理方式 |
| --- | --- |
| 运行形态 | 单用户、本机运行 |
| 登录态来源 | `app.env`、本地浏览器同步、单份 storage state |
| 目录策略 | 先保留平台级目录，避免一次性上多账号隔离 |
| 来源绑定 | 暂不引入来源到账号的显式绑定模型 |
| 失效处理 | 继续统一标记 `needs_reauth`，但只针对当前单用户 |

当前阶段必须遵守的规则：

| 规则 | 原因 |
| --- | --- |
| 单用户登录态集中管理 | 避免 Cookie、storage state 分散在各策略里 |
| 单平台状态文件位置固定 | 便于失效排查和手工修复 |
| 失效统一标记 `needs_reauth` | 避免登录失效后盲重试 |

后续如果进入多人、多账号阶段，再升级为正式账号体系：

| 对象 | 说明 |
| --- | --- |
| `Platform` | 站点，如 B 站、X、招聘后台等 |
| `SiteAccount` | 某站点的一份具体账号 |
| `AuthProfile` | 该账号对应的 Cookie、storage state、user-data-dir 等登录材料 |
| `SourceBinding` | 某个来源绑定到哪份账号态 |

## 6. 调度治理

调度层不是简单定时器，而是整个系统的稳定性治理中心。

| 模块 | 职责 |
| --- | --- |
| `Scheduler` | 触发任务 |
| `Execution Queue` | 控制排队和并发 |
| `Retry Controller` | 决定哪些错误可重试 |
| `Rate Limiter` | 控制平台级、账号级、来源级频率 |
| `Circuit Breaker` | 持续异常时自动暂停 |
| `Timeout Guard` | 防止单任务拖垮系统 |

标准失败分类如下：

| 分类 | 是否重试 | 系统动作 |
| --- | --- | --- |
| `network_error` | 是 | 短退避后重试 |
| `site_timeout` | 是 | 有上限重试 |
| `parse_error` | 否 | 标记策略待修复 |
| `auth_expired` | 否 | 标记 `needs_reauth` |
| `risk_control` | 限次 | 长退避，必要时熔断 |
| `permission_denied` | 否 | 标记来源或账号异常 |

## 7. 站点策略插件化

每个站点通过插件方式接入，框架只认统一接口，不内嵌站点细节。

| 插件接口 | 作用 |
| --- | --- |
| `strategy_id` | 唯一标识 |
| `validate_source()` | 校验来源配置 |
| `build_execution_plan()` | 返回执行路径 |
| `fetch()` | 取原始数据 |
| `parse()` | 输出统一结构化内容 |
| `classify_error()` | 将站点特有异常映射为标准失败类型 |

插件边界如下：

| 负责 | 不负责 |
| --- | --- |
| 取数 | 全局调度 |
| 解析 | 全局限速 |
| 站点特有错误识别 | 全局重试策略 |
| 站点字段转换 | 数据库存储控制 |

## 8. 数据处理中心

系统需要将抓取结果从原始记录提升为可共享内容对象。

| 对象 | 说明 |
| --- | --- |
| `RawItem` | 原始抓取结果，保留来源痕迹 |
| `ContentItem` | 清洗、去重、归一化后的共享内容 |

数据处理中心关键模块如下。

| 模块 | 职责 |
| --- | --- |
| `Normalizer` | 统一字段结构 |
| `Deduplicator` | 跨来源去重 |
| `Enricher` | 打标签、主题分类、业务线归类 |
| `Scoring` | 为内容打业务价值分 |

当前仓库中的最小落地入口如下。

| 入口 | 用途 |
| --- | --- |
| `/content-center` | 内容中心页面入口 |
| `/api/content` | 归一化内容查询接口 |
| `ReportService -> ContentPipelineService` | 任务完成后先写入 `RawItem` / `ContentItem`，再保留报告兼容输出 |

## 9. 订阅推送中心

系统以主动分发为主，因此推送必须建立在 `ContentItem` 之上，而不是直接推送原始采集结果。

| 模块 | 职责 |
| --- | --- |
| `Subscription` | 定义谁关心什么内容 |
| `Matcher` | 匹配内容和订阅规则 |
| `Dispatcher` | 投递到钉钉、邮件等渠道 |
| `DeliveryRecord` | 记录是否成功发送、是否重复、何时发送 |

订阅维度建议优先支持：

| 维度 | 示例 |
| --- | --- |
| 业务线 | 人事、市场、运营 |
| 标签 | 招聘、竞品、推广、投放 |
| 关键词 | 校招、招商、买量、合作 |
| 推送频率 | 实时、日报、周报 |

当前仓库中的最小落地入口如下。

| 入口 | 用途 |
| --- | --- |
| `/subscriptions` | 订阅中心页面入口 |
| `/api/subscriptions` | 订阅查询与创建接口 |
| `ContentDispatchService.dispatch_content_item()` | 以 `ContentItem` 为输入生成 `DeliveryRecord`，避免重复发送 |

## 10. 技术路线选择

当前技术路线定为：

| 层 | 技术 |
| --- | --- |
| 核心内核 | Python |
| 浏览器自动化 | Playwright for Python |
| API / 页面 | FastAPI |
| 主入口 | Web |
| 桌面壳 | 后续可选 Tauri / Electron |

关键决策如下：

| 决策 | 结论 |
| --- | --- |
| 是否全量迁到 Electron | 不迁 |
| 是否改成 Node.js 内核 | 不改 |
| 是否现在就做桌面壳 | 不作为主线 |
| 是否继续用 Python | 是 |

原因是系统复杂度主要在采集治理、数据处理和订阅推送，而不是桌面壳本身。

## 11. 分阶段实施路线图

| 阶段 | 目标 | 重点模块 |
| --- | --- | --- |
| Phase 1 | 稳定采集内核 | 单用户登录态治理、失败分类、调度控制、策略接口统一 |
| Phase 2 | 建立数据处理中心基础 | RawItem、ContentItem、清洗、去重、标签 |
| Phase 3 | 建立订阅推送中心 | 订阅规则、匹配、推送、投递记录 |
| Phase 4 | 建立共享视图 | 内容列表、筛选、状态页、推送管理 |
| Phase 5 | 按需补桌面壳或多账号体系 | 本地登录、托盘、快捷入口，或升级到多人账号模型 |

截至 2026-04-24，Phase 1~3 已完成最小闭环，Phase 4 已有 `/content-center` 与 `/subscriptions` 两个入口页，但筛选、状态跟踪和运营管理仍需继续补齐。

## 12. 当前明确不做的事情

为避免系统前期过度设计，当前明确不做以下内容：

| 暂不做 | 原因 |
| --- | --- |
| 全量重写到 Electron / Node | 迁移成本高，收益不匹配 |
| 复杂推荐系统 | 先用规则订阅即可 |
| 复杂权限体系 | 当前阶段先做基础角色隔离 |
| 多账号登录体系 | 当前阶段先按单用户运行，避免前期过度设计 |
| 动态插件市场 | 先用显式 registry |
| 过早拆成微服务 | 当前单体内核更稳、更快 |

## 13. 关键结论

| 结论 | 内容 |
| --- | --- |
| 系统定位 | 从单机采集工具升级为稳定采集框架、数据处理中心和订阅推送中心 |
| 核心技术路线 | 继续使用 Python Core + Playwright + FastAPI |
| 主入口形态 | Web 优先 |
| 桌面策略 | 后续按需补壳，不主导当前架构 |
| 当前重点 | 先把采集治理、数据处理、订阅分发做稳 |
