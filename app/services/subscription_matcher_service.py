from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import Subscription


class SubscriptionMatcherService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def match(self, content_item) -> list[Subscription]:
        subscriptions = list(
            self.session.scalars(
                select(Subscription)
                .where(Subscription.enabled.is_(True))
                .order_by(Subscription.code.asc())
            ).all()
        )
        matched: list[Subscription] = []
        content_tags = {str(tag).strip().lower() for tag in getattr(content_item, "tags", []) or [] if str(tag).strip()}
        haystack = " ".join(
            [
                str(getattr(content_item, "title", "") or ""),
                str(getattr(content_item, "excerpt", "") or ""),
                str(getattr(content_item, "canonical_url", "") or ""),
            ]
        ).lower()

        for subscription in subscriptions:
            business_lines = {
                str(value).strip().lower()
                for value in getattr(subscription, "business_lines", []) or []
                if str(value).strip()
            }
            keywords = [
                str(value).strip().lower()
                for value in getattr(subscription, "keywords", []) or []
                if str(value).strip()
            ]
            business_line_matches = not business_lines or bool(content_tags & business_lines)
            keyword_matches = not keywords or any(keyword in haystack for keyword in keywords)
            if business_line_matches and keyword_matches:
                matched.append(subscription)

        return matched
