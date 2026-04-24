# 70 数据库与 Alembic 迁移

状态：草案（阶段 3.1 落地）

## 70.1 现状

`app/db.py` 启动时执行 `Base.metadata.create_all` + 手工 `ensure_schema_compatibility(engine)`，通过 ALTER TABLE 向旧库补列。无版本记录、无回滚能力。

## 70.2 目标（REQ-MIG-001）

引入 Alembic：

| 项     | 决策                                                                                             |
| ------ | ------------------------------------------------------------------------------------------------ |
| 目录   | 仓库根 `alembic/` + `alembic.ini`                                                                |
| 基线   | `0001_baseline.py` 把当前所有模型 + `ensure_schema_compatibility` 中的列翻译为初始迁移           |
| 后续   | 模型变更 → `alembic revision --autogenerate -m "..."`                                            |
| 启动   | `app/main.py` 与 `launcher.py` 启动前执行 `alembic upgrade head`；可由 `AUTO_MIGRATE=false` 关闭 |
| 升级前 | 自动调用 `BackupService.backup_database()` 备份                                                  |
| 兼容期 | 保留 `ensure_schema_compatibility` 1 个版本，标记 `DeprecationWarning`；下个版本删除             |

## 70.3 SQLite 迁移注意

- SQLite 不支持 `ALTER TABLE DROP COLUMN`，迁移生成需用 `batch_alter_table` 模式。
- `alembic env.py` 自动检测 driver 并启用 batch 模式。

## 70.4 回滚

`alembic downgrade -1` 必须可执行；新增字段需提供反向 drop（SQLite 走 batch）。

## 70.5 数据备份

| 时机                     | 行为                                               |
| ------------------------ | -------------------------------------------------- |
| 启动前若检测到待执行迁移 | 自动备份到 `data/backups/auto-pre-migrate-<ts>.db` |
| 运维手工                 | `scripts/backup_database.ps1`                      |

## 70.6 验证

`TC-MIG-*`。
