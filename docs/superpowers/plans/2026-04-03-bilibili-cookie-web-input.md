# B站 Cookie 网页录入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户可以在 `/scheduler` 页面粘贴整串 B站 Cookie，由系统严格校验、自动规范化并写入 `app.env`，后续采集直接使用最新值。

**Architecture:** 继续复用 `AppEnvService` 作为 `app.env` 的唯一写入口，把 B站 Cookie 规范化和严格校验封装到服务层，再由 `/scheduler/bilibili` 表单提交调用。页面层只负责回显输入、展示成功或失败提示，并在失败时不重定向以保留用户输入。

**Tech Stack:** Python, FastAPI, server-rendered HTML, pytest

---

## 文件分工

| 文件 | 责任 |
| --- | --- |
| `app/services/app_env_service.py` | 负责 B站 Cookie 的规范化、严格校验、写入 `app.env`、同步更新进程环境变量 |
| `app/api/routes_pages.py` | 负责 `/scheduler` 页面消息展示、B站表单提交成功/失败分支、错误时保留输入 |
| `tests/unit/test_app_env_service.py` | 覆盖 B站 Cookie 规范化与严格校验 |
| `tests/integration/test_pages.py` | 覆盖页面保存成功、失败提示、输入保留、成功消息展示 |
| `docs/bilibili-cookie-运维说明.md` | 把操作入口更新成网页粘贴，不再主推手工改 `app.env` |

## Task 1: 为 B站 Cookie 规范化写失败测试

**Files:**
- Modify: `tests/unit/test_app_env_service.py`
- Test: `tests/unit/test_app_env_service.py`

- [ ] **Step 1: 为前缀自动提取写失败测试**

```python
def test_app_env_service_normalizes_prefixed_bilibili_cookie(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    settings = AppEnvService(env_file=env_file).update_bilibili_settings(
        cookie='BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'
    )

    assert settings.cookie == 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_app_env_service.py::test_app_env_service_normalizes_prefixed_bilibili_cookie -v`

Expected: FAIL，当前实现会把 `BILIBILI_COOKIE=` 原样写入。

- [ ] **Step 3: 为引号和换行规范化写失败测试**

```python
def test_app_env_service_normalizes_quoted_multiline_bilibili_cookie(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    settings = AppEnvService(env_file=env_file).update_bilibili_settings(
        cookie='"  SESSDATA=test-sess;\\n bili_jct=test-jct;\\n DedeUserID=123  "'
    )

    assert settings.cookie == 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'
```

- [ ] **Step 4: 运行测试确认失败**

Run: `pytest tests/unit/test_app_env_service.py::test_app_env_service_normalizes_quoted_multiline_bilibili_cookie -v`

Expected: FAIL，当前实现不会去外层引号，也不会压平换行。

- [ ] **Step 5: 为严格校验写失败测试**

```python
import pytest


def test_app_env_service_rejects_bilibili_cookie_without_sessdata(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    service = AppEnvService(env_file=env_file)

    with pytest.raises(ValueError, match='SESSDATA'):
        service.update_bilibili_settings(cookie='bili_jct=test-jct; DedeUserID=123')
```

- [ ] **Step 6: 运行测试确认失败**

Run: `pytest tests/unit/test_app_env_service.py::test_app_env_service_rejects_bilibili_cookie_without_sessdata -v`

Expected: FAIL，当前实现不会抛错。

## Task 2: 在服务层实现最小规范化与严格校验

**Files:**
- Modify: `app/services/app_env_service.py`
- Test: `tests/unit/test_app_env_service.py`

- [ ] **Step 1: 添加最小实现接口**

在 `AppEnvService` 中增加一个只负责处理 B站 Cookie 的辅助方法，例如：

```python
def _normalize_bilibili_cookie(self, raw_cookie: str) -> str:
    normalized = raw_cookie.strip()
    if normalized.startswith('"') and normalized.endswith('"'):
        normalized = normalized[1:-1]
    if normalized.startswith("'") and normalized.endswith("'"):
        normalized = normalized[1:-1]
    normalized = " ".join(normalized.split())
    if normalized.startswith('BILIBILI_COOKIE='):
        normalized = normalized.split('=', 1)[1].strip()
    if 'SESSDATA=' not in normalized:
        raise ValueError('Cookie 缺少 SESSDATA')
    return normalized
```

- [ ] **Step 2: 在 `update_bilibili_settings` 中接入规范化**

```python
normalized_cookie = self._normalize_bilibili_cookie(cookie)
values['BILIBILI_COOKIE'] = normalized_cookie
os.environ['BILIBILI_COOKIE'] = normalized_cookie
```

- [ ] **Step 3: 运行单元测试确认通过**

Run: `pytest tests/unit/test_app_env_service.py -v`

Expected: PASS，新增的 B站 Cookie 测试和原有测试都通过。

- [ ] **Step 4: 仅在必要时补一个“空字符串”测试**

```python
def test_app_env_service_rejects_empty_bilibili_cookie(tmp_path, monkeypatch) -> None:
    ...
    with pytest.raises(ValueError, match='不能为空'):
        service.update_bilibili_settings(cookie='   ')
```

- [ ] **Step 5: 再跑对应测试确认通过**

Run: `pytest tests/unit/test_app_env_service.py -v`

Expected: PASS。

## Task 3: 先写页面层失败测试，再实现成功/失败反馈

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: 为成功提示写失败测试**

```python
def test_scheduler_page_shows_bilibili_success_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-success-banner.db"))

    response = client.get('/scheduler?bilibili_saved=1')

    assert response.status_code == 200
    assert 'B站登录态已更新' in response.text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/integration/test_pages.py::test_scheduler_page_shows_bilibili_success_message -v`

Expected: FAIL，当前页面不会读取成功查询参数。

- [ ] **Step 3: 为非法 Cookie 不重定向写失败测试**

```python
def test_saving_invalid_bilibili_cookie_shows_error_without_writing_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-invalid.db"))

    response = client.post(
        '/scheduler/bilibili',
        data={'bilibili_cookie': 'bili_jct=test-jct; DedeUserID=123'},
        follow_redirects=False,
    )

    env_file = get_runtime_paths(tmp_path).env_file

    assert response.status_code == 422
    assert 'Cookie 缺少 SESSDATA' in response.text
    assert "bili_jct=test-jct; DedeUserID=123" in response.text
    assert not env_file.exists() or 'BILIBILI_COOKIE=' not in env_file.read_text(encoding='utf-8')
```

- [ ] **Step 4: 运行测试确认失败**

Run: `pytest tests/integration/test_pages.py::test_saving_invalid_bilibili_cookie_shows_error_without_writing_env -v`

Expected: FAIL，当前路由总是 `303` 跳转并写入。

- [ ] **Step 5: 为前缀自动规范化写失败测试**

```python
def test_saving_prefixed_bilibili_cookie_normalizes_before_writing_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-prefixed.db"))

    response = client.post(
        '/scheduler/bilibili',
        data={'bilibili_cookie': 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'},
        follow_redirects=False,
    )

    env_text = get_runtime_paths(tmp_path).env_file.read_text(encoding='utf-8')

    assert response.status_code == 303
    assert 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123' in env_text
```

- [ ] **Step 6: 运行测试确认失败**

Run: `pytest tests/integration/test_pages.py::test_saving_prefixed_bilibili_cookie_normalizes_before_writing_env -v`

Expected: FAIL，当前会把前缀一起写进去。

- [ ] **Step 7: 在 `routes_pages.py` 中抽出调度页渲染辅助函数**

把 `/scheduler` 页面的内容拼装收敛到一个内部函数，例如：

```python
def _render_scheduler_page(
    session: Session,
    *,
    bilibili_form_value: str | None = None,
    bilibili_error: str | None = None,
    bilibili_success: str | None = None,
) -> str:
    ...
```

目的：GET 与 POST 失败分支共用同一套页面渲染逻辑。

- [ ] **Step 8: 在调度页支持成功消息**

在 `GET /scheduler` 中读取 `request.query_params.get('bilibili_saved')`，生成成功提示 HTML，提示文案为：

```python
"B站登录态已更新"
```

- [ ] **Step 9: 在 `POST /scheduler/bilibili` 中接住 `ValueError`**

```python
try:
    AppEnvService().update_bilibili_settings(cookie=bilibili_cookie)
except ValueError as exc:
    html = _render_scheduler_page(
        session,
        bilibili_form_value=bilibili_cookie,
        bilibili_error=str(exc),
    )
    return HTMLResponse(html, status_code=422)
return RedirectResponse(url='/scheduler?bilibili_saved=1', status_code=303)
```

- [ ] **Step 10: 更新 B站表单说明文案**

将帮助文案改成说明支持：

```text
直接粘贴整串 Cookie；如果误贴了 BILIBILI_COOKIE= 前缀，系统会自动识别；缺少 SESSDATA 将拒绝保存。
```

- [ ] **Step 11: 运行集成测试确认通过**

Run: `pytest tests/integration/test_pages.py -v`

Expected: PASS，新增 B站保存成功/失败测试和原有页面测试均通过。

## Task 4: 更新运维说明，避免继续指导用户手工改 `app.env`

**Files:**
- Modify: `docs/bilibili-cookie-运维说明.md`

- [ ] **Step 1: 把配置入口文案统一到网页**

把“配置入口”改成明确的网页路径，例如：

```text
系统调度页 -> B站登录态（/scheduler）
```

- [ ] **Step 2: 把系统内填写要求改成网页粘贴模型**

明确说明：

```text
直接粘贴整串 Cookie
如果误贴了 BILIBILI_COOKIE= 前缀，系统会自动识别
缺少 SESSDATA 会拒绝保存
```

- [ ] **Step 3: 自查文档**

Run: `Get-Content -Raw "docs\\bilibili-cookie-运维说明.md"`

Expected: 文档不再主推手工编辑 `app.env` 作为首选操作。

## Task 5: 做最小验证并确认发布版需要重打包

**Files:**
- Test: `tests/unit/test_app_env_service.py`
- Test: `tests/integration/test_pages.py`
- Review: `release/HotCollector/HotCollectorLauncher.exe`

- [ ] **Step 1: 运行单元与集成测试**

Run: `pytest tests/unit/test_app_env_service.py tests/integration/test_pages.py -v`

Expected: PASS。

- [ ] **Step 2: 源码启动本地验证**

Run:

```powershell
.\.venv\Scripts\python.exe launcher.py --host 127.0.0.1 --port 38124 --no-browser --runtime-root .\temp_runtime_source_check
```

Expected: 打开 `http://127.0.0.1:38124/scheduler` 后，B站面板可见、非法输入有错误提示、合法输入保存成功。

- [ ] **Step 3: 记录发布版差异**

记录当前已知事实：

```text
release/HotCollector/HotCollectorLauncher.exe 当前版本的 /scheduler 页面不包含 B站 Cookie 输入框
```

- [ ] **Step 4: 如需交付给运营，重新打发布包**

参考已有打包脚本，完成后再次验证：

```powershell
http://127.0.0.1:<port>/scheduler
```

Expected: 新发布版与源码行为一致。

## 备注

| 项目 | 说明 |
| --- | --- |
| Git 提交 | 当前工作目录不是 git 仓库，执行时跳过提交步骤 |
| 子代理评审 | 当前会话没有得到你对“启用子代理”的明确授权，因此本计划未执行计划文档评审代理流程 |
