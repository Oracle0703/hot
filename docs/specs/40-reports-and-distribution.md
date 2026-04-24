# 40 报告生成与分发

状态：草案（阶段 3.1 加并发安全）

## 40.1 输出形式

| 输出              | 路径                                   | 说明           |
| ----------------- | -------------------------------------- | -------------- |
| 任务报告 Markdown | `outputs/reports/job-<id>.md`          | 单任务         |
| 任务报告 DOCX     | `outputs/reports/job-<id>.docx`        | 单任务         |
| 全局滚动报告      | `outputs/reports/hot-report.{md,docx}` | 跨任务去重合并 |
| 共享目录          | `outputs/shared-reports/`              | 复制脚本目标   |

## 40.2 全局报告并发安全（REQ-RPT-001）

阶段 3.1 起：

1. 写前对 `hot-report.md.lock` 加 `portalocker` 独占锁。
2. 内容写入临时文件 `hot-report.md.tmp.<pid>`，`os.replace` 原子替换。
3. DOCX 同理；写失败时保留临时文件供排障。

## 40.3 分发渠道

| 渠道              | 触发                                  | 配置                                      |
| ----------------- | ------------------------------------- | ----------------------------------------- |
| 钉钉 Webhook 摘要 | 任务完成自动发送                      | `ENABLE_DINGTALK_NOTIFIER` + `DINGTALK_*` |
| 共享目录复制      | 手动 `scripts/copy_latest_report.ps1` | `REPORT_SHARE_DIR`                        |
| 手动下载          | 报告页                                | 浏览器下载                                |

## 40.4 失败可见性

钉钉发送结果写入 `report_distribution_*` 表；首页系统状态卡片显示最近一次失败原因（脱敏）。

## 40.5 验证

`TC-RPT-*`。
