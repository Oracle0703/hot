# 30 调度、分发、取消与并发

状态：已落地（force=true 协作收口于 §30.3）

## 30.1 角色

| 模块                  | 职责                                         |
| --------------------- | -------------------------------------------- |
| `SchedulerLoop`       | 后台线程按 `SCHEDULER_POLL_SECONDS` 轮询     |
| `SchedulerService`    | 决定是否到达触发时间，避免同日重复触发       |
| `SchedulePlanService` | 多计划管理（按分组/时间）                    |
| `JobDispatcher`       | 任务出队 + 提交后台执行；维护 `cancel_event` |
| `JobRunner`           | 串行执行任务下属来源；写状态、日志、进度     |

## 30.2 触发流程

```
SchedulerLoop.tick()
 └─ SchedulerService.run_due_jobs(now)
     ├─ 命中计划 → JobService.create_scheduled_job(...)
     └─ JobDispatcher.dispatch_pending_jobs()
         └─ JobRunner.run(job)
             ├─ for source in sources:
             │    └─ SourceExecutionService.execute(source)  (策略分发)
             └─ ReportService.upsert_for_job(job)
```

## 30.3 取消（REQ-DISP-010）

| 行为           | 说明                                                          |
| -------------- | ------------------------------------------------------------- |
| 入口           | `POST /system/jobs/cancel-running`，可选 `force=true`         |
| 默认（协作式） | 设置 `cancel_event`；当前来源跑完后停止，任务标记 `cancelled` |
| `force=true`   | 中断 httpx / Playwright 调用，立即标记 `cancelled`            |
| 守护           | 30 秒未到 `cancelled` 状态则记录 warning，运维可强制重启      |

## 30.4 并发约束

- 同一时刻仅允许一个 `running` 任务；新触发任务进入 `pending`。
- 报告写入加文件锁（见 [40-reports-and-distribution.md](40-reports-and-distribution.md)）。

## 30.5 重试

由策略 + Source 级 `retry_policy` 决定（见 [20-collection-strategies.md](20-collection-strategies.md) §20.7）。Dispatcher 不做整任务级重试。

## 30.6 调度自检

`/system/health/extended` 暴露：

| 字段                        | 含义                         |
| --------------------------- | ---------------------------- |
| `scheduler.alive`           | 后台线程是否存活             |
| `scheduler.last_tick_at`    | 最近一次 tick 时间           |
| `scheduler.next_due_at`     | 下一次预计触发时间           |
| `dispatcher.running_job_id` | 当前运行任务 ID（无则 null） |

## 30.7 验证

`TC-SCHED-*`、`TC-DISP-*`。
