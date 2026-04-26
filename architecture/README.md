# 架构文档索引

本目录用于存放系统的中长期架构设计、关键决策和实施路线图，不再与日常使用说明、打包说明、运营说明混放。

## 阅读顺序

| 顺序 | 文档 | 作用 |
| --- | --- | --- |
| 1 | [2026-04-24-stable-crawling-data-center-architecture.md](./2026-04-24-stable-crawling-data-center-architecture.md) | 当前总架构蓝图 |
| 2 | [roadmap/2026-q2-implementation-roadmap.md](./roadmap/2026-q2-implementation-roadmap.md) | 近期实施路线图 |
| 3 | [adr/ADR-001-keep-python-core.md](./adr/ADR-001-keep-python-core.md) | 保留 Python Core 的决策 |
| 4 | [adr/ADR-002-web-first-desktop-shell-later.md](./adr/ADR-002-web-first-desktop-shell-later.md) | Web 优先、桌面壳后置的决策 |

## 文档边界

| 类型 | 放置位置 | 说明 |
| --- | --- | --- |
| 架构设计 | `architecture/` | 说明为什么这样设计、系统如何演进 |
| 实施计划 | `architecture/roadmap/` | 说明阶段目标、范围和节奏 |
| 架构决策记录 | `architecture/adr/` | 固化关键决策，减少反复讨论 |
| 使用说明 / 运行说明 | `README.md`、`docs/` | 说明如何启动、配置、打包、运营 |

## 更新规则

| 规则 | 说明 |
| --- | --- |
| 架构方向变化 | 更新总架构文档，必要时补充 ADR |
| 实施顺序变化 | 更新路线图文档 |
| 临时讨论结论 | 不直接写入正式文档，先收敛后再落文档 |
| 日常使用说明 | 仍维护在 `README.md` 或原有 `docs/` |
