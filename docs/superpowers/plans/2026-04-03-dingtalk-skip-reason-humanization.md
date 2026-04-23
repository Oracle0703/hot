# DingTalk Skip Reason Humanization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让任务详情页和进度面板把“无新增跳过钉钉通知”的英文 skip reason 显示成人话提示。

**Architecture:** 仅修改 `app/api/routes_pages.py` 中的诊断文案映射，复用现有 `dingtalk notification skipped` 解析链路，不改变通知服务、runner、报告生成或页面结构。测试通过页面集成用例覆盖最终展示文案。

**Tech Stack:** Python, FastAPI page rendering, pytest

---

### Task 1: 锁定页面文案行为

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: 写失败测试**

```python
def test_job_detail_page_humanizes_dingtalk_skip_for_no_new_items(tmp_path) -> None:
    assert "本轮无新增内容，已跳过钉钉通知。" in response.text
```

- [ ] **Step 2: 运行测试确认当前失败**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\integration\\test_pages.py -k "no_new_items" -v`
Expected: FAIL，因为当前页面仍显示通用“未发送”提示。

- [ ] **Step 3: 实现最小文案映射**

```python
if "no new collected items in current job" in lowered:
    return "本轮无新增内容，已跳过钉钉通知。"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\integration\\test_pages.py -k "no_new_items" -v`
Expected: PASS

### Task 2: 回归诊断摘要相关页面

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `app/api/routes_pages.py`

- [ ] **Step 1: 运行诊断摘要页面回归**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\integration\\test_pages.py -k "dingtalk or diagnostic_summary" -v`
Expected: PASS

- [ ] **Step 2: 运行应用导入链检查**

Run: `.\\.venv\\Scripts\\python.exe -c "import launcher; from app.main import create_app; create_app(start_background_workers=False); print('ok')"`
Expected: 输出 `ok`
