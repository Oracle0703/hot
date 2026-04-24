from __future__ import annotations

from app.services.retry_policy import RetryPolicy
from app.services.strategies import build_collection_strategy, run_awaitable_sync
from app.services.strategies.registry import ReasonCode, StrategyError


class SourceExecutionService:
    def __init__(self, registry, strategy_factory=None) -> None:
        self.registry = registry
        self.strategy_factory = strategy_factory or build_collection_strategy

    def execute(self, source) -> dict[str, object]:
        policy = RetryPolicy.from_dict(getattr(source, "retry_policy", None))
        return policy.run(lambda: self._execute_once(source))

    def _execute_once(self, source) -> dict[str, object]:
        strategy_name = getattr(source, "collection_strategy", None) or "generic_css"
        try:
            if strategy_name == "generic_css":
                return self._execute_generic(source)

            strategy = self.strategy_factory(strategy_name)
            if strategy is None or not hasattr(strategy, "execute"):
                raise ValueError(f"unsupported collection strategy: {strategy_name}")

            items = strategy.execute(source)
            if not isinstance(items, list):
                raise ValueError(f"collection strategy {strategy_name} must return a list of items")
            return {
                "item_count": len(items),
                "items": items,
            }
        except StrategyError:
            raise
        except (TimeoutError,) as exc:
            raise StrategyError(ReasonCode.TIMEOUT, str(exc), cause=exc)
        except (ConnectionError, OSError) as exc:
            raise StrategyError(ReasonCode.NETWORK, str(exc), cause=exc)

    def _execute_generic(self, source) -> dict[str, object]:
        collector = self.registry.get_collector(source)
        parser = self.registry.get_parser(source)
        html = run_awaitable_sync(collector.fetch(source))
        items = parser.parse(source, html)
        if not isinstance(items, list):
            raise ValueError("generic parser must return a list of items")
        return {
            "item_count": len(items),
            "items": items,
        }
