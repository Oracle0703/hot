from __future__ import annotations

from bs4 import BeautifulSoup


class GenericCssParser:
    def parse(self, source, html: str) -> list[dict[str, str | None]]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, str | None]] = []
        seen_urls: set[str] = set()
        include_keywords = list(getattr(source, "include_keywords", []) or [])
        exclude_keywords = list(getattr(source, "exclude_keywords", []) or [])
        max_items = int(getattr(source, "max_items", 30) or 30)

        for node in soup.select(getattr(source, "list_selector")):
            title_node = node.select_one(getattr(source, "title_selector"))
            link_node = node.select_one(getattr(source, "link_selector"))
            meta_node = node.select_one(getattr(source, "meta_selector")) if getattr(source, "meta_selector", None) else None

            if title_node is None or link_node is None:
                continue

            title = title_node.get_text(strip=True)
            url = (link_node.get("href") or "").strip()
            published_at = meta_node.get_text(strip=True) if meta_node is not None else None
            text_for_match = f"{title} {published_at or ''}"

            if include_keywords and not any(keyword in text_for_match for keyword in include_keywords):
                continue
            if exclude_keywords and any(keyword in text_for_match for keyword in exclude_keywords):
                continue
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            items.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                }
            )

            if len(items) >= max_items:
                break

        return items
