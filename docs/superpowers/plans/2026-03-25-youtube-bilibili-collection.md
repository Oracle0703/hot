# YouTube 与 B站专用采集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有通用采集链路上新增 YouTube 频道近一年采集和 B站站内搜索采集，并补充默认样例来源与自动化测试。

**Architecture:** 保留 `generic_css` 现有执行链路，在 `SourceExecutionService` 中基于 `collection_strategy` 分流到专用策略执行器。新策略以 Playwright 为主，返回与现有报告链路兼容的统一 item 结构。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Pydantic, pytest, Playwright

---

## 文件结构

| 路径 | 职责 |
| --- | --- |
| `app/models/source.py` | 扩展来源模型字段 |
| `app/schemas/source.py` | 扩展 API 输入输出 schema |
| `app/api/routes_sources.py` | 让表单入口支持新字段 |
| `app/services/source_execution_service.py` | 根据 `collection_strategy` 分流执行 |
| `app/services/source_service.py` | 保持 CRUD，并承接初始化来源时的存储逻辑 |
| `app/services/strategies/__init__.py` | 策略模块导出 |
| `app/services/strategies/youtube_channel_recent.py` | YouTube 专用策略 |
| `app/services/strategies/bilibili_site_search.py` | B站专用策略 |
| `app/main.py` | 应用启动时补齐默认样例来源 |
| `tests/integration/test_sources_api.py` | 新字段 CRUD 回归 |
| `tests/unit/test_source_execution_service.py` | 执行分流测试 |
| `tests/unit/test_strategy_youtube_channel_recent.py` | YouTube 策略单测 |
| `tests/unit/test_strategy_bilibili_site_search.py` | B站策略单测 |
| `tests/unit/test_source_seed.py` | 默认样例来源测试 |

### Task 1: 扩展来源配置模型

**Files:**
- Modify: `app/models/source.py`
- Modify: `app/schemas/source.py`
- Modify: `app/api/routes_sources.py`
- Test: `tests/integration/test_sources_api.py`

- [ ] **Step 1: 写失败测试，覆盖新字段创建与读取**
- [ ] **Step 2: 运行失败测试，确认因字段缺失失败**
  Run: `python -m pytest tests\integration\test_sources_api.py -q`
- [ ] **Step 3: 最小化实现模型与 schema 变更**
- [ ] **Step 4: 更新 API 表单映射，支持新字段**
- [ ] **Step 5: 重新运行相关测试，确认通过**
  Run: `python -m pytest tests\integration\test_sources_api.py -q`

### Task 2: 为执行服务增加策略分流

**Files:**
- Modify: `app/services/source_execution_service.py`
- Create: `app/services/strategies/__init__.py`
- Create: `app/services/strategies/youtube_channel_recent.py`
- Create: `app/services/strategies/bilibili_site_search.py`
- Test: `tests/unit/test_source_execution_service.py`

- [ ] **Step 1: 写失败测试，验证按 `collection_strategy` 分流**
- [ ] **Step 2: 运行测试，确认因为不支持 strategy_factory 失败**
  Run: `python -m pytest tests\unit\test_source_execution_service.py -q`
- [ ] **Step 3: 最小化实现分流与策略注入**
- [ ] **Step 4: 重新运行测试，确认通过**
  Run: `python -m pytest tests\unit\test_source_execution_service.py -q`

### Task 3: 实现 YouTube 专用策略

**Files:**
- Create: `app/services/strategies/youtube_channel_recent.py`
- Test: `tests/unit/test_strategy_youtube_channel_recent.py`

- [ ] **Step 1: 写失败测试，覆盖最近一年过滤与三类结果去重**
- [ ] **Step 2: 运行测试，确认因为策略不存在或行为未实现失败**
  Run: `python -m pytest tests\unit\test_strategy_youtube_channel_recent.py -q`
- [ ] **Step 3: 实现最小可测逻辑**
- [ ] **Step 4: 补充 Playwright 抽象边界，避免单测依赖真实浏览器**
- [ ] **Step 5: 重新运行测试，确认通过**
  Run: `python -m pytest tests\unit\test_strategy_youtube_channel_recent.py -q`

### Task 4: 实现 B站站内搜索策略

**Files:**
- Create: `app/services/strategies/bilibili_site_search.py`
- Test: `tests/unit/test_strategy_bilibili_site_search.py`

- [ ] **Step 1: 写失败测试，覆盖查询词拼接与前 30 条截断**
- [ ] **Step 2: 运行测试，确认失败**
  Run: `python -m pytest tests\unit\test_strategy_bilibili_site_search.py -q`
- [ ] **Step 3: 最小化实现**
- [ ] **Step 4: 加入必要校验**
- [ ] **Step 5: 重新运行测试，确认通过**
  Run: `python -m pytest tests\unit\test_strategy_bilibili_site_search.py -q`

### Task 5: 补充默认样例来源初始化

**Files:**
- Modify: `app/main.py`
- Modify: `app/services/source_service.py`
- Test: `tests/unit/test_source_seed.py`

- [ ] **Step 1: 写失败测试，验证样例来源幂等写入**
- [ ] **Step 2: 运行测试，确认因缺少 seed 逻辑失败**
  Run: `python -m pytest tests\unit\test_source_seed.py -q`
- [ ] **Step 3: 最小化实现初始化逻辑**
- [ ] **Step 4: 在应用启动路径中调用 seed**
- [ ] **Step 5: 重新运行测试，确认通过**
  Run: `python -m pytest tests\unit\test_source_seed.py -q`

### Task 6: 执行回归验证

**Files:**
- Test: `tests/integration/test_sources_api.py`
- Test: `tests/unit/test_source_execution_service.py`
- Test: `tests/unit/test_strategy_youtube_channel_recent.py`
- Test: `tests/unit/test_strategy_bilibili_site_search.py`
- Test: `tests/unit/test_source_seed.py`

- [ ] **Step 1: 运行新增与相关回归测试**
  Run: `python -m pytest tests\integration\test_sources_api.py tests\unit\test_source_execution_service.py tests\unit\test_strategy_youtube_channel_recent.py tests\unit\test_strategy_bilibili_site_search.py tests\unit\test_source_seed.py -q`
- [ ] **Step 2: 修复失败项直到全绿**
- [ ] **Step 3: 运行更大范围回归**
  Run: `python -m pytest -q`
- [ ] **Step 4: 准备手动联调说明**
