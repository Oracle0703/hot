# 21 解析器与字段映射

状态：草案

## 21.1 解析器分类

| 类型     | 实现                                           | 适用场景                              |
| -------- | ---------------------------------------------- | ------------------------------------- |
| 通用 CSS | `app/collectors/parsers/generic_css_parser.py` | 服务器端渲染、列表清晰的站点          |
| 站点专用 | `app/services/strategies/<site>.py` 内嵌       | API 接口、复杂登录态、Playwright 交互 |

## 21.2 字段映射约定

| `ItemDTO` 字段                                             | 必填 | 来源                                                       |
| ---------------------------------------------------------- | ---- | ---------------------------------------------------------- |
| `title`                                                    | 是   | `title_selector` 或 API                                    |
| `url`                                                      | 是   | `link_selector`，自动转绝对路径                            |
| `published_at`                                             | 否   | `meta_selector` 文本解析；解析失败回落 `published_at_text` |
| `published_at_text`                                        | 否   | 原始时间文本，用于显示                                     |
| `excerpt`                                                  | 否   | 摘要                                                       |
| `heat_score` / `view_count` / `like_count` / `reply_count` | 否   | 站点 API 字段                                              |
| `cover_image_url`                                          | 否   | 封面                                                       |
| `image_urls`                                               | 否   | 多图正文                                                   |
| `author`                                                   | 否   | 作者                                                       |
| `raw_payload`                                              | 否   | 原始解析结果（用于排障）                                   |

## 21.3 归一化与去重

- URL 归一化：去 `utm_*`、统一协议为 `https`、去末尾 `/`。
- `normalized_hash = sha1(url_normalized + title_normalized)`，用于 `collected_items.normalized_hash`。
- 同一任务内重复以最早出现为准；跨任务以 `first_seen_at` 记录首次发现。

## 21.4 错误回填

| 场景         | 处理                                               |
| ------------ | -------------------------------------------------- |
| 选择器未命中 | `diagnostics.title_hits=0`，整批丢弃且记录 warning |
| 字段缺失     | 跳过单条，整批继续                                 |
| 编码异常     | 强制 `utf-8` 容错解码，记录 warning                |

## 21.5 验证

`TC-STRAT-101~120`、`TC-STRAT-201~215`。
