# DingTalk Skip Empty New Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让钉钉通知仅在当前任务存在新增内容时发送，无新增时跳过并写入明确日志。

**Architecture:** 保持发送条件内聚在 `DingTalkWebhookService` 内，通过查询 `CollectedItem.first_seen_job_id == job.id` 判断当前任务是否有新增内容，并把“无新增”暴露为 skip reason。`JobRunner` 继续沿用现有 skipped 日志分支，不改报告生成和页面逻辑。

**Tech Stack:** Python, SQLAlchemy, FastAPI runtime services, pytest

---

### Task 1: 固化无新增跳过发送的服务层行为

**Files:**
- Modify: `tests/unit/test_dingtalk_webhook_service.py`
- Modify: `app/services/dingtalk_webhook_service.py`

- [ ] **Step 1: 写失败测试，覆盖“无新增时不发钉钉”**

```python
def test_dingtalk_webhook_service_skips_when_current_job_has_no_new_items(tmp_path) -> None:
    assert service.notify_job_summary(second_job) is False
    assert requests == []
    assert service.get_skip_reason() == "no new collected items in current job"
```

- [ ] **Step 2: 运行测试确认当前失败**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_dingtalk_webhook_service.py -k "no_new_items" -v`
Expected: FAIL，因为当前实现仍会发送。

- [ ] **Step 3: 实现最小逻辑**

```python
def notify_job_summary(self, job: CollectionJob) -> bool:
    self._last_skip_reason = None
    config_skip_reason = self._get_config_skip_reason()
    if config_skip_reason is not None:
        self._last_skip_reason = config_skip_reason
        return False
    if self._count_new_items(job) == 0:
        self._last_skip_reason = "no new collected items in current job"
        return False
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_dingtalk_webhook_service.py -k "no_new_items" -v`
Expected: PASS

### Task 2: 固化 runner 的跳过日志

**Files:**
- Modify: `tests/unit/test_runner.py`
- Modify: `app/workers/runner.py`

- [ ] **Step 1: 写失败测试，覆盖“第二轮无新增时写 skipped 日志”**

```python
def test_runner_logs_warning_when_dingtalk_notification_is_skipped_for_no_new_items(...):
    assert any(
        log.level == "warning"
        and "dingtalk notification skipped: no new collected items in current job" in log.message
        for log in logs
    )
```

- [ ] **Step 2: 运行测试确认当前失败**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_runner.py -k "no_new_items" -v`
Expected: FAIL，因为当前第二轮仍会走发送。

- [ ] **Step 3: 用真实通知逻辑通过测试**

```python
monkeypatch.setattr(DingTalkWebhookService, "_send_webhook", fake_send)
runner.run_once()  # 第一轮有新增
runner.run_once()  # 第二轮无新增
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_runner.py -k "no_new_items" -v`
Expected: PASS

### Task 3: 完整回归

**Files:**
- Modify: `app/services/dingtalk_webhook_service.py`
- Modify: `tests/unit/test_dingtalk_webhook_service.py`
- Modify: `tests/unit/test_runner.py`

- [ ] **Step 1: 运行钉钉与 runner 相关单测**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\test_dingtalk_webhook_service.py tests\\unit\\test_runner.py -v`
Expected: PASS

- [ ] **Step 2: 运行关键页面/启动回归**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\integration\\test_pages.py -k "dingtalk or diagnostic_summary" -v`
Expected: PASS

- [ ] **Step 3: 运行应用导入链检查**

Run: `.\\.venv\\Scripts\\python.exe -c "import launcher; from app.main import create_app; create_app(start_background_workers=False); print('ok')"`
Expected: 输出 `ok`
