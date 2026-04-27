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

### `GET /system/desktop-manifest`

为后续桌面壳或本地启动器提供稳定入口清单，避免在客户端硬编码导航路径。
对应的 JSON Schema 文件已提交到 `docs/specs/desktop-manifest.schema.json`，可直接用于桌面壳侧离线校验或生成类型。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `kind` | string | 固定为 `desktop-shell-manifest` |
| `entry_route` | string | Web 主入口 |
| `info_route` | string | 系统信息接口 |
| `health_route` | string | 扩展健康检查接口 |
| `docs_route` | string | FastAPI 文档入口 |
| `navigation[]` | array | 推荐导航项，包含 `id` / `label` / `href` |
| `service.entry_url` | string | 当前实例的绝对首页 URL |
| `service.desktop_manifest_url` | string | 当前 manifest 的绝对 URL |
| `service.health_url` | string | 当前实例健康检查绝对 URL |
| `service.docs_url` | string | 当前实例 API 文档绝对 URL |
| `runtime.runtime_root` | string | 当前运行根目录 |
| `runtime.reports_root` | string | 报告目录 |
| `runtime.pid_file` | string | 启动器 PID 文件位置 |
| `control.launch` | object | 本地启动入口，包含 `launcher_path`、`source_entry_path`、`release_bat_path`、`preferred_path`、`launch_mode`、`preferred_args`、`default_args` |
| `control.probe` | object | 本地状态探测入口，包含 `script_path`、`release_bat_path`、`preferred_path`、`launch_mode`、`preferred_args`、`default_args` |
| `control.stop` | object | 本地停止入口，包含 `script_path`、`release_bat_path`、`preferred_path`、`launch_mode`、`preferred_args`、`default_args` |

### `GET /system/auth-state`

返回当前多账号账号态快照。首版只覆盖 B站登录态，用于 `/auth-state` 页面与桌面壳状态展示。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 总状态：`ok` / `warning` / `missing` / `error` |
| `runtime_root` | string | 当前运行根目录 |
| `checked_at` | string | 本次快照生成时间 |
| `platforms[]` | array | 平台状态列表，首版只有一个 `bilibili` |

平台对象字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `platform` | string | 平台标识，首版固定 `bilibili` |
| `display_name` | string | 展示名，首版固定 `B站` |
| `status` | string | 平台聚合状态 |
| `action_hint` | string | 当前平台优先建议动作 |
| `issues` | array | 当前平台聚合问题列表 |
| `accounts[]` | array | 账号列表，至少包含默认账号快照 |

账号对象字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `account_id` | string/null | 账号主键；默认兼容账号可能为空 |
| `account_key` | string | 账号稳定键，如 `default`、`creator-a` |
| `display_name` | string | 展示名 |
| `enabled` | bool | 是否启用 |
| `is_default` | bool | 是否默认账号 |
| `status` | string | 账号状态 |
| `cookie_configured` | bool | 当前账号 Cookie 是否已配置 |
| `storage_state_exists` | bool | 当前账号 storage state 是否存在 |
| `user_data_dir_exists` | bool | 当前账号 user-data 目录是否存在 |
| `storage_state_file` | string | 当前账号 storage state 文件路径 |
| `user_data_dir` | string | 当前账号浏览器用户目录路径 |
| `action_hint` | string | 建议动作 |
| `issues` | array | 当前账号问题列表 |

### `GET /api/site-accounts`

返回账号列表，支持 `?platform=bilibili` 过滤。

### `POST /api/site-accounts`

创建账号槽位。请求体字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `platform` | string | 首版固定 `bilibili` |
| `account_key` | string | 账号稳定键，会规范化为小写短横线形式 |
| `display_name` | string | 展示名 |
| `enabled` | bool | 是否启用 |
| `is_default` | bool | 是否设为默认账号 |

### `POST /system/jobs/cancel-running`

| 入参    | 类型         | 说明                                    |
| ------- | ------------ | --------------------------------------- |
| `force` | bool（可选） | 默认 `false`（协作式）；`true` 立即中断 |

响应：`{ "cancelled_job_id": "..." }` 或 `{ "cancelled_job_id": null, "reason": "no_running_job" }`。

### `GET /system/config/export?mask=true`

返回 yaml 文本（`Content-Type: text/yaml`）。`mask=false` 仅在 DEBUG 模式可用，且会记录审计日志。

## 报告与周榜（Reports / Weekly）

### `GET /api/reports`

返回当前历史报告列表。

### `GET /api/reports/{report_id}/download?format=md|docx`

下载指定报告文件。

| 查询参数 | 类型 | 说明 |
| --- | --- | --- |
| `format` | string | `md` 或 `docx`，默认 `md` |

### `GET /weekly`

返回最近 7 天热点周榜页面。

| 页面能力 | 说明 |
| --- | --- |
| 数据范围 | 仅展示最近 7 天首次抓到的内容 |
| 排序 | 优先按发布时间倒序；缺失时降级按首次采集时间 |
| 扩展信息 | 页面会同步展示推荐评分、人工评分控件与推送状态 |
| 封面读取 | 页面中的封面图片统一走 `/weekly/covers/{item_id}` 本地缓存入口 |

### `POST /weekly/ratings`

保存当前周榜页上的人工评分选择。

| 请求体 | 类型 | 说明 |
| --- | --- | --- |
| `grade_{item_id}` | form field | 每条内容的人工评分；空值表示清空 |

成功后返回 `303`，重定向到 `/weekly?ratings_saved=1`。

### `POST /weekly/push`

批量推送当前最近 7 天窗口内、达到阈值且尚未推送的内容到钉钉。

| 行为 | 说明 |
| --- | --- |
| 推荐评分刷新 | 推送前会先刷新当前窗口内条目的推荐评分并持久化 |
| 阈值来源 | `WEEKLY_GRADE_PUSH_THRESHOLD` |
| 去重规则 | 已写入 `pushed_to_dingtalk_at` 的内容不会重复推送 |
| 成功跳转 | `303 -> /weekly?pushed_count={n}` |
| 空结果跳转 | `303 -> /weekly?push_empty=1` |

### `GET /weekly/covers/{item_id}`

返回指定条目的本地封面缓存文件；找不到条目或缓存文件时返回 `404`。

## 采集源与任务

详见 `app/api/routes_sources.py`、`routes_jobs.py` 与 [../specs/20-collection-strategies.md](20-collection-strategies.md)。本节后续继续补全业务说明。
