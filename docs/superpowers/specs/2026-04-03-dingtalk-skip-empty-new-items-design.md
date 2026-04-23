# 钉钉通知在无新增时跳过发送设计

## 背景

当前系统在任务完成并生成报告后，只要钉钉开关开启且 Webhook 已配置，就会尝试发送一次任务摘要。  
这会带来一个明显的运维噪音问题：当本轮采集没有任何新增内容时，钉钉仍然会推送“热点报告更新”，但实际上没有新的热点值得关注。

用户已经明确要求采用严格规则：

| 项目 | 规则 |
| --- | --- |
| 是否发送钉钉 | 仅当本轮存在新增内容时发送 |
| “新增”的定义 | `CollectedItem.first_seen_job_id == 当前任务 ID` |
| 无新增时是否仍提醒失败/未命中 | 不提醒，直接不发 |

## 目标

| 项目 | 目标 |
| --- | --- |
| 发送条件 | 仅在当前任务产生至少 1 条新增内容时发送钉钉 |
| 跳过原因 | 当无新增时记录明确的 skip reason |
| 行为兼容 | 保持现有钉钉配置校验、签名、摘要格式不变 |
| 页面兼容 | 任务详情页继续沿用现有“钉钉通知未发送”诊断展示 |

## 非目标

| 项目 | 说明 |
| --- | --- |
| 修改报告生成逻辑 | 不改变全局报告文件写法和内容 |
| 修改新增判定规则 | 不引入按标题、热度、时间等新口径 |
| 改造通知渠道抽象 | 不扩展到邮件、企业微信等其它通知方式 |
| 新增页面开关 | 不增加“无新增也发送”的可选配置 |

## 设计方案

### 推荐方案

在 `DingTalkWebhookService` 内部增加“本轮新增条数”判断：

| 步骤 | 行为 |
| --- | --- |
| 1 | 进入 `notify_job_summary(job)` 时先清空上一次 skip reason |
| 2 | 先检查现有配置跳过原因，如未启用或缺少 Webhook |
| 3 | 统计 `CollectedItem.first_seen_job_id == job.id` 的记录数 |
| 4 | 如果新增数为 0，则设置 skip reason 为 `no new collected items in current job` 并返回 `False` |
| 5 | 如果新增数大于 0，则继续构造 payload 并发送 |

该方案把通知发送条件继续收口在通知服务内部，避免 runner、report service、页面层分别维护自己的判断规则。

### 不采用的方案

| 方案 | 不采用原因 |
| --- | --- |
| 在 `ReportService` 上挂新增数 | 增加无关职责，侵入更大 |
| 在 `JobRunner` 直接查询新增数 | 让发送条件分散到调用侧，后续更难维护 |

## 详细行为

### 新增判定

| 条件 | 结果 |
| --- | --- |
| `first_seen_job_id == 当前 job.id` 的数量大于 0 | 允许发送钉钉 |
| `first_seen_job_id == 当前 job.id` 的数量等于 0 | 跳过发送 |

### Skip Reason 规则

保留现有配置类 skip reason，同时新增业务类 skip reason：

| 场景 | skip reason |
| --- | --- |
| 钉钉开关关闭但配置了 Webhook | `ENABLE_DINGTALK_NOTIFIER is false` |
| 已启用但未配置 Webhook | `DINGTALK_WEBHOOK is empty` |
| 当前任务无新增 | `no new collected items in current job` |

`notify_job_summary()` 在返回 `False` 后，`get_skip_reason()` 必须能拿到本次真正的跳过原因，供 runner 写入任务日志。

## 任务日志行为

当本轮没有新增时，runner 应继续记录 warning 日志：

| 字段 | 内容 |
| --- | --- |
| level | `warning` |
| message | `dingtalk notification skipped: no new collected items in current job` |

这能让任务详情页和诊断摘要继续解释“为什么本轮没有发钉钉”。

## 数据流

| 阶段 | 数据 |
| --- | --- |
| 任务完成 | `JobRunner` 拿到当前 `job` |
| 报告生成后 | `DingTalkWebhookService.notify_job_summary(job)` 被调用 |
| 新增统计 | 查询 `CollectedItem.first_seen_job_id == job.id` |
| 无新增 | 返回 `False`，记录 skip reason |
| 有新增 | 按现有逻辑构造 Markdown 摘要并发给钉钉 |

## 测试设计

### 单元测试

| 用例 | 预期 |
| --- | --- |
| 当前任务有新增 | 正常发送，返回 `True` |
| 当前任务无新增 | 不发送，返回 `False`，并暴露 skip reason |
| 配置未启用或缺少 Webhook | 继续维持原有 skip 逻辑 |

### Runner 测试

| 用例 | 预期 |
| --- | --- |
| 第二次任务只有重复命中、没有新增 | 任务仍为 success，但写入 `dingtalk notification skipped: no new collected items in current job` |

## 风险与权衡

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| 某轮没有新增但有严重抓取失败 | 也不会发钉钉 | 这是用户明确要求的严格模式，后续如需例外再单独加配置 |
| skip reason 状态残留 | 可能污染下一次调用 | 每次 `notify_job_summary()` 开始前重置内部状态 |

## 验收标准

| 编号 | 标准 |
| --- | --- |
| 1 | 当本轮新增条数为 0 时，钉钉 webhook 不会被调用 |
| 2 | 此时 `notify_job_summary()` 返回 `False` |
| 3 | runner 会记录 `dingtalk notification skipped: no new collected items in current job` |
| 4 | 当本轮存在新增内容时，现有钉钉发送能力保持正常 |
