# 80 测试规范

状态：已落地（v1）

## 80.1 分层

| 层     | 目录                                 | 范围                                       |
| ------ | ------------------------------------ | ------------------------------------------ |
| 单元   | `tests/unit/`                        | 服务、模型、配置、解析器、策略；不依赖网络 |
| 集成   | `tests/integration/`                 | FastAPI 路由 + DB + 文件系统               |
| 端到端 | `tests/e2e/`                         | 配置 → 试抓 → 任务 → 报告 → 钉钉 mock      |
| 脚本   | `tests/integration/test_scripts*.py` | PS1 脚本 `-DryRun` 回归                    |

## 80.2 命名规范（REQ-TEST-001）

- 用例 ID：`TC-<域>-<3 位序号>`，例 `TC-CFG-001`，与 [../test-cases.md](../test-cases.md) 一一对应。
- 测试方法名：`test_<行为>_<场景>`，docstring 第一行写 `TC-XXX-NNN: 一句话场景`，便于 `pytest --collect-only` grep。

## 80.3 骨架与待实现

新增测试文件先生成骨架：

```python
import pytest

class TestConfigSchema:
    @pytest.mark.skip(reason="TC-CFG-001 待实现")
    def test_default_values_loaded_when_env_missing(self) -> None:
        """TC-CFG-001: 进程未设置任何环境变量时返回 schema 默认值"""
```

`pytest --collect-only` 必须能列出全部 TC 编号。已实现的用例移除 `skip`。

## 80.4 公共夹具

`tests/conftest.py` 已提供：

- `create_test_client(database_url)` — 隔离 DB 的 FastAPI TestClient
- `make_sqlite_url(tmp_path, name)` — 临时 SQLite URL
- `_derive_runtime_root` — 自动设置 `HOT_RUNTIME_ROOT`

阶段 2/3 增加：

- `temp_app_env(tmp_path, fields=None)` — 写入临时 `app.env` 并切换 `HOT_RUNTIME_ROOT`
- `mock_strategy_registry()` — 注入 demo 策略
- `cancel_event_factory()` — 提供可控取消事件

## 80.5 Mock 边界

- 网络：禁止真实出站；统一使用 `respx`（httpx）或 `pytest-httpx`；Playwright 走 `tests/fixtures/*.html` 文件读取。
- 钉钉：默认 mock；端到端冒烟使用 `dingtalk://mock` 模式。
- 时间：使用 `freezegun` 或固定 `datetime` 注入。

## 80.6 覆盖率目标

| 模块               | 目标  |
| ------------------ | ----- |
| `app/services/*`   | ≥ 80% |
| `app/api/*`        | ≥ 70% |
| `app/collectors/*` | ≥ 70% |
| 整体               | ≥ 75% |

`scripts/run_tests.ps1` 一键跑 `pytest --cov=app --cov-report=term-missing`。

## 80.7 验证

参见 [../test-cases.md](../test-cases.md)。
