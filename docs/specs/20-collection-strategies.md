# 20 采集策略抽象与扩展

状态：草案（阶段 3.2 落地）

## 20.1 现状与目标

当前 `Source.collection_strategy` 字段在 `app/services/source_execution_service.py` 内 if/elif 分流到 B站、YouTube、X、generic_css 各路径，错误处理不统一。阶段 3.2 引入统一接口与注册机制，新增策略仅新建一个文件即可。

## 20.2 接口（REQ-STRAT-001）

```
class CollectionStrategy(Protocol):
    name: str

    def describe(self) -> StrategyMeta: ...
    def validate_config(self, source: Source) -> list[ValidationIssue]: ...
    def fetch(self, source: Source, ctx: ExecutionContext) -> list[ItemDTO]: ...
    def dry_run(self, source: Source, ctx: ExecutionContext) -> DryRunResult: ...
```

| 类型               | 说明                                                                |
| ------------------ | ------------------------------------------------------------------- | ---------------- |
| `StrategyMeta`     | `name / display_name / required_fields / supports_login / docs_url` |
| `ValidationIssue`  | `field / level (error                                               | warn) / message` |
| `ExecutionContext` | `http_client / playwright / settings / logger / cancel_event`       |
| `ItemDTO`          | 与 `collected_items` 列对齐的 dataclass                             |
| `DryRunResult`     | `items[<=5] / diagnostics[]`，包含选择器命中数与丢弃原因            |

## 20.3 注册（REQ-STRAT-002）

`app/services/strategies/registry.py` 提供：

```
@register("bilibili_profile_videos_recent")
class BilibiliProfileVideosRecent(CollectionStrategy): ...
```

`SourceExecutionService.execute(source)` 在运行时只做：解析名称 → `registry.get(name)` → `strategy.fetch(...)` → 异常归一为 `StrategyError(reason_code, message, hint)`。

## 20.4 异常分类

| `reason_code` | 含义                  | 处理建议              |
| ------------- | --------------------- | --------------------- |
| `NETWORK`     | 连接/超时/DNS         | 适用重试              |
| `AUTH`        | Cookie/Token 失效     | 提示重新登录          |
| `RATE_LIMIT`  | 限流/风控             | 退避重试              |
| `PARSE`       | 选择器未命中/字段缺失 | 试抓诊断              |
| `CONFIG`      | 配置非法              | 配置中心校验阻拦      |
| `UNKNOWN`     | 其他                  | 记录堆栈到 DEBUG 日志 |

## 20.5 取消支持（REQ-STRAT-003）

`fetch` 内每次大循环检查 `ctx.cancel_event.is_set()`，命中即抛 `StrategyCancelled`，由 Dispatcher 统一处理。

## 20.6 试抓（REQ-STRAT-010）

| 接口                                  | 用途                |
| ------------------------------------- | ------------------- |
| `POST /api/sources/dry-run`（未保存） | 校验前端表单 + 试抓 |
| `POST /api/sources/{id}/dry-run`      | 已保存的源试抓      |

返回结构：`{ "items": [...], "diagnostics": { "list_hits": N, "title_hits": N, "filtered_out": N, "warnings": [] } }`。

## 20.7 重试策略（REQ-STRAT-020）

`Source.retry_policy` 字段（JSON）：

```
{ "max_attempts": 3, "backoff_seconds": 5, "retry_on": ["NETWORK", "RATE_LIMIT"] }
```

JobRunner 按指数退避执行，日志记录 `attempt=1/3 reason=NETWORK`。

## 20.8 验证

`TC-STRAT-*`、`TC-DISP-*` 见 [../test-cases.md](../test-cases.md)。
