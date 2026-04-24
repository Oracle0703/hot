# 热点采集系统规格文档（docs/specs/）

> 版本：v1（2026-04-23 启用）
> 上一版规格快照：[../../spec.md](../../spec.md)、[../../plan.md](../../plan.md)（已冻结）
> 变更记录：[../../CHANGELOG.md](../../CHANGELOG.md)
> 测试用例总表：[../test-cases.md](../test-cases.md)

## 文档导航

| 编号 | 文档                                                             | 主题                              |
| ---- | ---------------------------------------------------------------- | --------------------------------- |
| 00   | [00-overview.md](00-overview.md)                                 | 系统总览 / 角色 / 基座定位        |
| 10   | [10-runtime-and-config.md](10-runtime-and-config.md)             | 运行时路径、配置 Schema、配置中心 |
| 20   | [20-collection-strategies.md](20-collection-strategies.md)       | 采集策略抽象与扩展                |
| 21   | [21-parsers.md](21-parsers.md)                                   | 解析器与字段映射                  |
| 30   | [30-scheduling-and-dispatch.md](30-scheduling-and-dispatch.md)   | 调度、分发、取消、并发            |
| 40   | [40-reports-and-distribution.md](40-reports-and-distribution.md) | 报告生成与分发                    |
| 50   | [50-system-and-ops.md](50-system-and-ops.md)                     | 系统页、备份/恢复、版本、日志     |
| 60   | [60-security.md](60-security.md)                                 | 配置加密、URL 白名单、登录态边界  |
| 70   | [70-database-and-migration.md](70-database-and-migration.md)     | 数据模型、Alembic 迁移            |
| 80   | [80-testing.md](80-testing.md)                                   | 测试分层、命名规范、夹具          |
| 90   | [90-release-and-upgrade.md](90-release-and-upgrade.md)           | 发布、升级、SHA256 完整性         |
| --   | [api-reference.md](api-reference.md)                             | 业务语境的 API 说明               |

## 文档约定

| 项目     | 约定                                                            |
| -------- | --------------------------------------------------------------- |
| 文件命名 | `<两位数编号>-<英文短名>.md`，编号步进 10，便于中间插入         |
| 章节编号 | `<文件编号>.<节序号>`，例如 `30.2 调度循环`                     |
| 需求编号 | `REQ-<域>-<序号>`，与测试用例 `TC-<域>-<序号>` 一一对应         |
| 决策记录 | 重大技术取舍仍写入 `docs/technical-decisions/` 并在 spec 中引用 |
| 状态标记 | 章节末尾用 `状态：草案 / 实施中 / 已落地 / 已弃用` 标注         |

## 写作流程

1. 新需求：先在对应主题文件追加 `REQ-<域>-<序号>` 条目并标记 `状态：草案`。
2. 用例同步：在 [../test-cases.md](../test-cases.md) 增补 `TC-<域>-<序号>` 行；如需 pytest 骨架，落到 `tests/` 下并 `@pytest.mark.skip(reason="TC-<编号> 待实现")`。
3. 实施完成：把状态改为 `已落地`，并在 [../../CHANGELOG.md](../../CHANGELOG.md) 的 `[Unreleased]` 节追加条目。
4. 发布：从 `[Unreleased]` 移到新版本节，更新 `app/services/version_service.py` 注入信息。

## 域代码

| 域      | 含义                     | 关联文件         |
| ------- | ------------------------ | ---------------- |
| `CFG`   | 配置 Schema 与配置中心   | 10               |
| `STRAT` | 采集策略与解析器         | 20 / 21          |
| `SCHED` | 调度与计划               | 30               |
| `DISP`  | 任务分发与取消           | 30               |
| `RPT`   | 报告生成与分发           | 40               |
| `SYS`   | 系统页、备份、版本、日志 | 50               |
| `SEC`   | 安全与合规               | 60               |
| `MIG`   | 数据库与迁移             | 70               |
| `API`   | HTTP 接口                | api-reference.md |
| `E2E`   | 端到端冒烟               | 80               |
