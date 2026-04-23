# YouTube 与 B站专用采集设计

## 背景

当前系统只支持基于 `entry_url + fetch_mode + parser_type + CSS selector` 的通用列表页采集。用户新增了两类更强约束的采集方式：

1. YouTube 频道采集：只提供频道 URL，抓取最近一年的内容，范围包含 `视频 + Shorts + Live`
2. B站站内搜索采集：提供站点 URL 和关键词，执行站内搜索，查询词自动拼接当天日期，只抓前 30 条

首批测试样例来源固定为：

- `https://www.youtube.com/@ElectronicArts`
- `https://www.youtube.com/@EpicGames`
- `https://www.bilibili.com/` + `search_keyword=游戏`

当前会话日期按 `2026-03-25` 处理，因此 B站查询词示例为 `游戏 2026-03-25`。

## 目标

- 在不破坏现有 `generic_css` 采集链路的前提下，新增两种专用采集策略
- 让来源配置能表达这两种新模式
- 将首批测试来源补充到系统初始化数据中，便于启动后直接验证
- 为后续真实页面联调保留手动测试入口，但不把外网不稳定行为放进默认自动化测试

## 方案选择

采用“策略分流”方案，而不是继续复用 parser：

- 在 `Source` 上新增 `collection_strategy`
- `generic_css` 继续走现有 `CollectorRegistry + parser`
- `youtube_channel_recent` 与 `bilibili_site_search` 走专用策略执行器

这样做的原因：

- 新需求不只是“换个解析器”，还包含页面导航、交互、滚动加载、时间过滤、结果去重
- 把这些逻辑塞进 parser 会模糊职责边界，并让现有通用采集链路变脆

## 数据模型设计

### Source 新增字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `collection_strategy` | string | `generic_css` / `youtube_channel_recent` / `bilibili_site_search` |
| `search_keyword` | string \| null | 仅 `bilibili_site_search` 使用 |

### 兼容策略

| 现有字段 | 处理方式 |
| --- | --- |
| `fetch_mode` | 保留；旧来源继续可用；新两种来源默认使用 `playwright` |
| `parser_type` | 保留；仅 `generic_css` 使用 |
| `entry_url` | YouTube 模式填频道 URL；B站模式填 `https://www.bilibili.com/` |
| `max_items` | YouTube 模式作为抓取上限；B站模式最终截断到 30 条 |

## 执行架构

### 分流规则

`SourceExecutionService.execute(source)` 先读取 `collection_strategy`：

- `generic_css`：沿用现有 registry/collector/parser 链路
- `youtube_channel_recent`：走 `YouTubeChannelRecentStrategy`
- `bilibili_site_search`：走 `BilibiliSiteSearchStrategy`

### 新增模块

建议新增目录 `app/services/strategies/`，至少包含：

- `youtube_channel_recent.py`
- `bilibili_site_search.py`
- `factory.py` 或简单的执行分发逻辑

`CollectorRegistry` 保持旧职责，不强行承接新策略。

## 具体行为

### YouTube 频道近一年采集

执行规则：

- 打开频道 URL
- 依次尝试抓取 `videos`、`shorts`、`streams` 三类内容
- 通过滚动加载更多结果
- 提取统一字段：`title`、`url`、`published_at`、`excerpt`、`raw_payload`
- 仅保留发布时间在“当前执行日向前 365 天”范围内的内容
- 以 URL 去重后返回
- 当已滚动到明显早于时间窗口的内容时提前停止深翻

### B站站内搜索采集

执行规则：

- 打开 `entry_url`，首版只支持 `https://www.bilibili.com/`
- 读取 `search_keyword`
- 生成查询词：`{search_keyword} {today}`，本次会话示例为 `游戏 2026-03-25`
- 在 B站站内搜索框输入并触发搜索
- 进入结果页后提取统一字段
- 结果只取前 30 条
- 以 URL 去重后返回

## 错误处理

应明确抛出可用于任务日志定位的问题，例如：

- `unsupported collection strategy`
- `bilibili search keyword is required`
- `bilibili site search currently only supports https://www.bilibili.com/`
- `youtube channel page structure changed`
- `bilibili search input not found`

## 测试策略

### 自动化测试

- 扩展 source API 测试，覆盖新增字段
- 扩展 `SourceExecutionService` 分流测试
- 为两个策略各写单元测试
- 使用 fake page / fake playwright 风格的测试替身，避免真实网络依赖
- 验证：
  - YouTube 时间窗口过滤
  - YouTube 三类内容合并去重
  - B站查询词拼接
  - B站结果截断到 30 条

### 非自动化测试

- 提供手动执行入口，用真实来源验证：
  - `https://www.youtube.com/@ElectronicArts`
  - `https://www.youtube.com/@EpicGames`
  - `https://www.bilibili.com/` + `游戏`
- 不将其纳入默认 pytest，避免外网、结构变更、风控导致回归不稳定

## 初始化样例来源

系统启动或初始化时补齐以下幂等样例：

| 名称 | `entry_url` | `collection_strategy` | `search_keyword` |
| --- | --- | --- | --- |
| `YouTube-ElectronicArts` | `https://www.youtube.com/@ElectronicArts` | `youtube_channel_recent` | `null` |
| `YouTube-EpicGames` | `https://www.youtube.com/@EpicGames` | `youtube_channel_recent` | `null` |
| `B站-游戏-今日搜索` | `https://www.bilibili.com/` | `bilibili_site_search` | `游戏` |

要求：

- 按名称或唯一组合做幂等去重
- 不覆盖用户已修改的来源

## 影响范围

预计涉及：

- `app/models/source.py`
- `app/schemas/source.py`
- `app/services/source_execution_service.py`
- `app/services/source_service.py`
- `app/api/routes_sources.py`
- `app/main.py` 或初始化入口
- `tests/unit/*`
- `tests/integration/*`

## 已知边界

- 首版 B站搜索只支持 B站首页入口，不做通用站内搜索框架
- 首版 YouTube/B站 都优先用 Playwright，稳定优先，不追求极限性能
- 真实页面解析依赖外网和站点结构，自动化测试只覆盖本地可控行为
