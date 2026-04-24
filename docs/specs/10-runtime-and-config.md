# 10 运行时与配置中心

状态：已落地（阶段 3.3 收口校验通过）

## 10.1 运行时路径

由 `app/runtime_paths.py` 统一暴露，源码运行时根目录为仓库根，PyInstaller 打包时为 exe 所在目录，可被 `HOT_RUNTIME_ROOT` 环境变量覆盖。

| 路径                   | 用途                                     |
| ---------------------- | ---------------------------------------- |
| `data/`                | 配置、SQLite、登录态、PID                |
| `data/app.env`         | 运行配置（敏感值启用时以 `enc:` 前缀密文写入同一文件） |
| `data/backups/`        | 数据库备份目录（阶段 1 引入）            |
| `logs/`                | 应用与启动器日志（阶段 1 起轮转）        |
| `outputs/reports/`     | 报告输出目录                             |
| `playwright-browsers/` | Playwright 浏览器目录                    |

## 10.2 配置加载优先级

```
进程环境变量 > data/app.env > 配置 Schema 默认值
```

## 10.3 配置 Schema（REQ-CFG-001）

阶段 2 在 `app/config_schema.py` 用 Pydantic v2 `BaseSettings` 统一定义，并由 `app/config.py` 兼容转发。每个字段提供：

| 元数据        | 说明                                                                                   |
| ------------- | -------------------------------------------------------------------------------------- |
| `default`     | 默认值                                                                                 |
| `description` | 说明（用于配置中心 UI 展示）                                                           |
| `group`       | 分组：`app / database / reports / scheduler / dingtalk / bilibili / network / source / weekly` |
| `sensitive`   | 是否敏感（影响掩码与加密）                                                             |
| `validator`   | 校验器（URL、`HH:MM`、整数范围、Cookie 必含 `SESSDATA=` 等）                           |

## 10.4 配置中心 UI（REQ-CFG-010）

系统提供独立 `/config` 配置中心页，按 `group` 分组渲染。敏感字段默认显示掩码（前 4 + `***` + 后 4）。

| 操作         | 行为                                              |
| ------------ | ------------------------------------------------- |
| 单字段保存   | 触发 schema 校验，失败返回 422 + 字段级错误       |
| 配置自检     | 钉钉测试消息、B站 Cookie 拉取一次 nav、代理可达性 |
| 导出脱敏配置 | `GET /system/config/export?mask=true` 返回 yaml   |

## 10.5 文件锁与原子写（REQ-CFG-020）

`app/services/app_env_service.py` 重写后必须满足：

1. 写入使用 `portalocker`（Windows / POSIX 兼容）独占锁，读取按 `utf-8-sig` 解析。
2. 写入采用“写临时文件 → `os.replace`”原子替换。
3. 缺失字段在读取时回退到 schema 默认值；当前版本不做旧 `app.env` 的自动备份迁移。

## 10.6 兼容性

- 保留 `app/config.py` 旧入口，转发到新 schema，旧调用方无需立即修改。
- 新字段必须给默认值；移除字段需在 `CHANGELOG.md` 显式说明并保留 1 个版本的兼容读取。

## 10.7 验证

参见 [../test-cases.md](../test-cases.md) `TC-CFG-*` 与 `tests/unit/test_config_schema.py`、`tests/unit/test_app_env_service.py`、`tests/integration/test_config_center_pages.py`。
