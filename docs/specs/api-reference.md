# API 参考（业务语境）

状态：已落地（覆盖系统页 + 待补全采集源/任务/报告业务说明）

> FastAPI 自动文档地址：本机 `http://127.0.0.1:38080/docs`。本文件补充业务语境与脱敏示例。

## 系统（System）

### `GET /system/info`

| 字段             | 类型            | 说明                            |
| ---------------- | --------------- | ------------------------------- |
| `version`        | string          | 应用语义版本                    |
| `commit`         | string          | Git 短哈希                      |
| `built_at`       | string(ISO8601) | 构建时间                        |
| `python_version` | string          | 运行 Python 版本                |
| `runtime_root`   | string          | 运行时根目录绝对路径            |
| `started_at`     | string(ISO8601) | 进程启动时间                    |
| `uptime_seconds` | number          | 运行秒数                        |
| `app_env`        | string          | `development` / `production` 等 |

示例响应：

```json
{
  "version": "1.0.0",
  "commit": "abc1234",
  "built_at": "2026-04-23T10:22:31+08:00",
  "python_version": "3.11.9",
  "runtime_root": "C:\\HotCollector",
  "started_at": "2026-04-23T11:00:00+08:00",
  "uptime_seconds": 3600.5,
  "app_env": "production"
}
```

### `GET /system/health/extended`

返回 `200` 表示全部健康；任一检测失败返回 `503`。

| 字段                     | 含义                                                  |
| ------------------------ | ----------------------------------------------------- | --------- |
| `database.ok`            | DB 连接是否成功                                       |
| `scheduler.alive`        | 调度线程是否存活                                      |
| `scheduler.last_tick_at` | 最近 tick 时间                                        |
| `disk.free_mb`           | 数据盘剩余 MB                                         |
| `cookies.bilibili.valid` | B站 Cookie 是否有效                                   |
| `dingtalk.last_status`   | 最近一次发送结果                                      |
| `issues[]`               | `{ "code": "...", "message": "...", "severity": "warn | error" }` |

### `POST /system/jobs/cancel-running`

| 入参    | 类型         | 说明                                    |
| ------- | ------------ | --------------------------------------- |
| `force` | bool（可选） | 默认 `false`（协作式）；`true` 立即中断 |

响应：`{ "cancelled_job_id": "..." }` 或 `{ "cancelled_job_id": null, "reason": "no_running_job" }`。

### `GET /system/config/export?mask=true`

返回 yaml 文本（`Content-Type: text/yaml`）。`mask=false` 仅在 DEBUG 模式可用，且会记录审计日志。

## 采集源、任务、报告

详见 `app/api/routes_sources.py`、`routes_jobs.py`、`routes_reports.py` 与 [../specs/20-collection-strategies.md](specs/20-collection-strategies.md)。本节随阶段 3 落地后补全。
