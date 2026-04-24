# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- 规格文档主题化:新增 `docs/specs/` 13 篇主题文件与 `docs/specs/README.md` 导航。
- 测试用例总表 `docs/test-cases.md`,统一编号 `TC-<域>-<序号>`。
- **阶段 1 — 运维基座**:
  - `scripts/stop.ps1`、`scripts/stop_system.bat` 仓库内停服脚本。
  - `scripts/backup_database.ps1`、`scripts/restore_database.ps1` 数据库一键备份/恢复(默认保留 14 份)。
  - `app/services/version_service.py` + 仓库根 `VERSION` 文件,支持构建期注入 `version/commit/built_at`。
  - `app/api/routes_system.py` 新增 `/system/info`、`/system/health/extended`、`/system/jobs/cancel-running`、`/system/config/export`。
  - 日志统一 `RotatingFileHandler`(10 MB × 5)覆盖 `launcher.log` / `app.log` / `scheduler.log`。
  - `scripts/build_package.ps1` 在 PyInstaller 完成后自动写入 `dist\HotCollectorLauncher\VERSION`(含 git commit 短哈希、构建时间、channel)。
- **阶段 2 — 配置写入并发安全**:
  - `app/services/app_env_service.py:_write_values` 切换为 `portalocker.Lock` + `tempfile + os.replace` 的"加锁→临时文件→原子替换"模式,消除两个写者同时改 `data/app.env` 时的字段丢失风险。
  - 新增并发写测试 `tests/unit/test_app_env_service.py::test_app_env_service_concurrent_writes_do_not_corrupt_file`。
- **阶段 3.1 — 报告并发安全**:
  - `app/services/report_service.py:_activate_prepared_report_files` 在 markdown_path 同目录创建 `.hot-report.lock`,以 `portalocker` 序列化所有 writer 的 `.bak` 与 `.replace` 切换。
  - 新增 `tests/unit/test_report_concurrency.py` 验证锁互斥与超时行为。
- **阶段 3.2 — 协作式取消**:
  - 新增 `app/services/cancel_registry.py`:`request_cancel/is_cancelled/consume/clear`。
  - `JobRunner` 在每个 source 边界检查 cancel 标志,被取消时记录 warning 日志、跳出剩余 source 并最终把任务状态置为 `cancelled`。
  - `/system/jobs/cancel-running` 实际接入注册表,返回 `mode=cooperative|force`,重复取消返回 `reason=already_cancelled`。
  - 新增 `tests/unit/test_job_dispatcher_cancel.py` 真实测试(含 JobRunner 全链路)。
- **阶段 4 — 安全加固**:
  - `app/schemas/source.py:SourceCreate/SourceUpdate` 增加 `entry_url` 协议白名单:生产仅 `http(s)`;DEBUG 允许 `file://` 以兼容本地 HTML 测试夹具。
  - `scripts/build_offline_release.ps1`、`scripts/build_upgrade_release.ps1` 末尾自动生成 `<release>.zip.sha256`(REQ-SEC-020)。
  - 新增 `app/services/config_encryption.py`:可选 Fernet 静态加密工具(`encrypt_text/decrypt_text/get_status/generate_key`),未设置 `CONFIG_ENCRYPTION_KEY` 时回退明文并 warn。AppEnvService 接入留待后续小步迭代。
- 测试骨架:`tests/unit/` `tests/integration/` `tests/e2e/` 下新增覆盖 CFG/SYS/STRAT/DISP/RPT/SEC/MIG/API/E2E 的 pytest 骨架(尚未实现的部分以 `pytest.mark.skip(reason="TC-... 待实现")` 占位,保证 `pytest --collect-only` 列出全部 TC 编号)。

### Changed

- `spec.md`、`plan.md` 头部增加冻结说明,仅保留 MVP 历史快照。
- `requirements.txt` 增补 `portalocker`、`cryptography`、`pyyaml`、`respx`(pytest mock)。
- `tests/integration/test_scripts.py::test_launcher_dry_run_prints_local_runtime_summary` 改用 `sys.executable` 启动子进程,避免命中系统 Python 的旧依赖。

### Deferred(后续版本继续)

- **强制中断任务**(REQ-DISP-102 / `force=true`):当前为协作式取消,强制 kill 留待阶段 4。
- **端到端冒烟**(TC-E2E-001~005):需要真浏览器 + 真服务的多进程编排,留待阶段 4。
- **运维脚本 dry-run 子进程驱动**(TC-SYS-201~205 / TC-API-301):需 PowerShell + Python 跨进程编排夹具,留待 1.2.0。
- **报告 docx 并发完整集成**(TC-RPT-003/004):需要完整 ReportService 集成夹具与生产观察。

### 阶段 3.2 — 深度重构闭环(本轮新增)

- **REQ-CFG-001/010 — Pydantic Settings**:
  - 新增 `app/config_schema.py`,以 `pydantic_settings.BaseSettings` 重新定义 9 个分组(app/database/reports/scheduler/dingtalk/bilibili/network/source/weekly),自带 `bool/int/url/HH:MM/SESSDATA` 校验、`mask_value`、`list_settings_groups`、`export_settings_yaml`、`self_check_dingtalk_webhook`。
  - `app/config.py:get_settings()` 改为优先使用 schema 校验,异常时回退到 `_legacy_get_settings`,保持向后兼容。
  - 新增 `tests/unit/test_config_schema.py`(15 个真测,替换原 skip)。
- **REQ-CFG-010 — 配置中心 UI**:
  - `app/api/routes_pages.py` 增加 `GET /config` 与 `POST /config`,按分组渲染 `<table class="config-table">`,提交后用 schema 校验、敏感字段自动 mask、错误以字段级 422 回显。
  - `tests/integration/test_config_center_pages.py` 3 个真测,覆盖渲染 / 422 / 持久化。
- **REQ-MIG-001 — Alembic 基线 + 自动迁移**:
  - 新增 `alembic.ini`、`migrations/env.py`(`disable_existing_loggers=False`,避免破坏 pytest caplog)、`migrations/versions/0001_baseline.py`、`migrations/versions/0002_retry_policy.py`。
  - 新增 `app/services/migration_service.py:run_migrations(...)` 返回 `MigrationResult{action, backup_path, pending_revisions}`,支持 `AUTO_MIGRATE` 开关与 sqlite 迁前自动备份;legacy DB 自动 stamp head。
  - `tests/unit/test_alembic_migrations.py` 5 个真测。
- **REQ-STRAT-001 — 采集策略统一抽象**:
  - 新增 `app/services/strategies/registry.py`:`StrategyRegistry`、`@register("name")` 装饰器、`StrategyMeta`、`StrategyResult`、`StrategyError(reason_code)`、`StrategyCancelled`、`StrategyAlreadyRegistered`、`StrategyNotFound`、`execute_with_cancel_check`,统一 `ReasonCode` 五元组(NETWORK/TIMEOUT/PARSE/AUTH/CANCELLED/UNKNOWN)。
  - `tests/unit/test_strategy_registry.py` 6 个真测(TC-STRAT-001~006)。
- **REQ-STRAT-002 — 试抓服务 + API**:
  - 新增 `app/services/dry_run_service.py:DryRunService`(默认截断 5 条,返回 `{items, diagnostics: list_hits/title_hits/filtered_out/capped_to/kept_total}`)。
  - `app/api/routes_sources.py` 新增 `POST /api/sources/dry-run` 与 `POST /api/sources/{id}/dry-run`,支持 `file://` 本地夹具(便于自测)。
  - `tests/unit/test_dry_run_service.py` 2 个真测,`tests/integration/test_dry_run_api.py` 2 个真测。
- **REQ-DISP-001 — 重试策略**:
  - `Source` 模型新增 `retry_policy: JSON` 字段,迁移 `0002_retry_policy`。
  - 新增 `app/services/retry_policy.py:RetryPolicy`(`max_attempts/retry_on/backoff_seconds`,指数退避 1s,2s,4s...),并接入 `SourceExecutionService.execute()`,自动把 `OSError/ConnectionError → NETWORK`、`TimeoutError → TIMEOUT`。
  - `tests/unit/test_retry_policy.py` 5 个真测(TC-DISP-001~005)。
- **REQ-SYS-040 — 首页系统状态卡片**:
  - `app/api/routes_pages.py:_render_system_status_card` 直接复用 `routes_system._check_database/_scheduler_state/_disk_free_mb/_running_job_id`,在首页渲染数据库 / 调度线程 / 磁盘 / 运行中任务四张状态卡。
- **REQ-OPS-003 — 任务指标服务**:
  - 新增 `app/services/metrics_service.py:compute_job_metrics(session, window_hours=24)` 返回 success_rate / p50 / p95 / avg。
  - `app/api/routes_system.py` 新增 `GET /system/metrics?window_hours=...`。
  - `tests/unit/test_metrics_service.py` 3 个真测。
- **REQ-SYS-101~103 — 应用日志轮转**:
  - 新增 `RuntimePaths.app_log_file = logs/app.log`、`app/services/log_setup.py:setup_app_logging(paths)`(RotatingFileHandler 10MB×5,幂等)。
  - `app/main.py:create_app` 启动期最佳努力安装。
  - `tests/unit/test_log_rotation.py` 3 个真测,覆盖 launcher.log 与 app.log。
- **TC-SYS-002 / TC-API-003 取消跳过**:`test_version_service.py::test_version_file_missing_falls_back_to_git_commit` 与 `test_system_api.py::test_health_extended_returns_503_on_db_failure` 转换为真测。
- **回归测试 / 时间格式冲突修复**:
  - 在 `app/services/dingtalk_webhook_service.py` 引入 `_truncate_seconds_in_text`,在钉钉行渲染前裁掉秒,与 `published_at_display.py` 的"显式秒保留"保持一致;两条相反预期的测试同时通过。

### Verification

- `pytest -q`: **339 passed / 17 skipped / 0 failed**(基线 286/60 → +53 真测 / -43 skip)。剩余 17 个 skip 全部为明确延后到阶段 4 / 1.2.0 的项目(E2E、ops 子进程、force-cancel、report 并发观察)。
- `pylanceFileSyntaxErrors` 在所有新增/修改文件上无错误。
- 文件链接:[app/config_schema.py](app/config_schema.py)、[app/services/strategies/registry.py](app/services/strategies/registry.py)、[app/services/dry_run_service.py](app/services/dry_run_service.py)、[app/services/retry_policy.py](app/services/retry_policy.py)、[app/services/metrics_service.py](app/services/metrics_service.py)、[app/services/log_setup.py](app/services/log_setup.py)、[app/services/migration_service.py](app/services/migration_service.py)、[migrations/versions/0001_baseline.py](migrations/versions/0001_baseline.py)、[migrations/versions/0002_retry_policy.py](migrations/versions/0002_retry_policy.py)。

### Deprecated

- `app/db.py:ensure_schema_compatibility` 计划在 Alembic 接入(1.1.0)后下一版本删除。

### Verification

- `pytest -q`: 286 passed / 60 skipped / 0 failed(对比基线 46 passed,新增 240 passed 含转换为真测的 19 个 + 新增覆盖)。
- `pytest --collect-only`: 341 items,docs/test-cases.md 全表 TC 编号可被收集。

---

## [1.0.0] - 2026-04-23

### Added

- MVP：采集源 CRUD、HTTP/Playwright 双模式、定时调度、Markdown/DOCX 报告、钉钉摘要、B 站登录态同步、PyInstaller 打包与离线/升级包发布脚本。
- 单元/集成测试基线 46 passed。

[Unreleased]: ./
[1.0.0]: ./
