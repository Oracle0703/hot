from __future__ import annotations

import asyncio
import threading
from typing import TypeVar

T = TypeVar("T")


def run_awaitable_sync(awaitable) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: dict[str, T] = {}
    error: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(awaitable)
        except BaseException as exc:  # pragma: no cover
            error["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error:
        raise error["error"]
    return result["value"]


from app.services.strategies.bilibili_profile_videos_recent import BilibiliProfileVideosRecentStrategy
from app.services.strategies.bilibili_site_search import BilibiliSiteSearchStrategy
from app.services.strategies.x_profile_recent import XProfileRecentStrategy
from app.services.strategies.youtube_channel_recent import YouTubeChannelRecentStrategy


def build_collection_strategy(strategy_name: str):
    if strategy_name == "youtube_channel_recent":
        return YouTubeChannelRecentStrategy()
    if strategy_name == "bilibili_site_search":
        return BilibiliSiteSearchStrategy()
    if strategy_name == "bilibili_profile_videos_recent":
        return BilibiliProfileVideosRecentStrategy()
    if strategy_name == "x_profile_recent":
        return XProfileRecentStrategy()
    raise ValueError(f"unsupported collection strategy: {strategy_name}")


__all__ = [
    "BilibiliProfileVideosRecentStrategy",
    "BilibiliSiteSearchStrategy",
    "YouTubeChannelRecentStrategy",
    "XProfileRecentStrategy",
    "build_collection_strategy",
    "run_awaitable_sync",
]
