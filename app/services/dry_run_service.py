"""阶段 3.2 — 试抓服务(REQ-STRAT-002 / TC-STRAT-301~302)。

目标:在不写库的前提下,根据 source 的当前配置抓取并解析,只保留前 N 条,
并返回足够帮助用户排错的诊断信息。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.collectors.parsers.generic_css_parser import GenericCssParser

DEFAULT_DRY_RUN_LIMIT = 5


@dataclass(slots=True)
class DryRunResult:
    items: list[dict[str, Any]]
    diagnostics: dict[str, Any]


class DryRunService:
    """通用试抓服务。

    `fetcher` 可注入,用于在测试中绕过真实 HTTP / Playwright。默认行为:
    * 调用 `fetcher(source) -> str`(返回 HTML)
    * 用 GenericCssParser 解析
    * 截断到 limit 条
    """

    def __init__(
        self,
        fetcher: Optional[Callable[[Any], str]] = None,
        parser: Optional[Any] = None,
        *,
        limit: int = DEFAULT_DRY_RUN_LIMIT,
    ) -> None:
        self._fetcher = fetcher
        self._parser = parser or GenericCssParser()
        self._limit = limit

    def dry_run(self, source: Any) -> DryRunResult:
        if self._fetcher is None:
            raise RuntimeError("DRY_RUN_REQUIRES_FETCHER: 未注入 fetcher,无法在生产路径外执行")
        html = self._fetcher(source)
        parsed = self._parser.parse(source, html)

        list_hits = len(parsed)
        title_hits = sum(1 for item in parsed if (item.get("title") or "").strip())
        # 关键词过滤(简化版:仅按 source.include/exclude_keywords)
        include = [k for k in (getattr(source, "include_keywords", None) or []) if k]
        exclude = [k for k in (getattr(source, "exclude_keywords", None) or []) if k]
        kept: list[dict[str, Any]] = []
        filtered_out = 0
        for item in parsed:
            title = (item.get("title") or "")
            if include and not any(k in title for k in include):
                filtered_out += 1
                continue
            if exclude and any(k in title for k in exclude):
                filtered_out += 1
                continue
            kept.append(item)

        capped = kept[: self._limit]
        diagnostics = {
            "list_hits": list_hits,
            "title_hits": title_hits,
            "filtered_out": filtered_out,
            "capped_to": self._limit,
            "kept_total": len(kept),
        }
        return DryRunResult(items=capped, diagnostics=diagnostics)


__all__ = ["DryRunService", "DryRunResult", "DEFAULT_DRY_RUN_LIMIT"]
