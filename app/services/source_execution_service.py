from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.api.routes_sources import SessionFactoryHolder
from app.services.app_env_service import AppEnvService
from app.services.retry_policy import RetryPolicy
from app.services.site_account_service import SiteAccountService
from app.services.strategies import build_collection_strategy, run_awaitable_sync
from app.services.strategies.registry import ReasonCode, StrategyError


class SourceExecutionService:
    def __init__(self, registry, strategy_factory=None, account_context_resolver=None) -> None:
        self.registry = registry
        self.strategy_factory = strategy_factory or build_collection_strategy
        self.account_context_resolver = account_context_resolver or self._default_account_context_resolver

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

            self._apply_account_context(source, strategy_name)
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

    def _apply_account_context(self, source, strategy_name: str) -> None:
        if not str(strategy_name or "").startswith("bilibili_"):
            return
        context = self.account_context_resolver(source) or {}
        for key, value in context.items():
            setattr(source, key, value)

    def _default_account_context_resolver(self, source) -> dict[str, str]:
        account_key = self._resolve_bilibili_account_key(source)
        return {
            "account_key": account_key,
            "account_cookie": AppEnvService().get_bilibili_settings(account_key=account_key).cookie,
        }

    def _resolve_bilibili_account_key(self, source) -> str:
        account_key = str(getattr(source, "account_key", "") or "").strip()
        if account_key:
            return account_key

        account = getattr(source, "account", None)
        if account is not None and getattr(account, "account_key", None):
            return str(account.account_key)

        factory = SessionFactoryHolder.factory
        if factory is None:
            return "default"

        account_id = getattr(source, "account_id", None)
        with factory() as session:
            service = SiteAccountService(session)
            try:
                if account_id is not None:
                    return service.ensure_account(str(account_id)).account_key
                default_account = service.get_default_account("bilibili")
                if default_account is not None:
                    return default_account.account_key
            except OperationalError:
                return "default"
        return "default"
