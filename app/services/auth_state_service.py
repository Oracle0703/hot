from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.runtime_paths import detect_runtime_root


@dataclass(slots=True)
class AuthStatePaths:
    user_data_dir: Path
    storage_state_file: Path


class AuthStateService:
    def __init__(self, runtime_root: str | Path | None = None) -> None:
        self.runtime_root = detect_runtime_root(runtime_root)

    def build_paths(self, platform: str, account_key: str = "default") -> AuthStatePaths:
        normalized_platform = self._normalize_platform(platform)
        normalized_account_key = self._normalize_account_key(account_key)
        data_dir = self.runtime_root / "data"
        if normalized_account_key == "default":
            return AuthStatePaths(
                user_data_dir=data_dir / f"{normalized_platform}-user-data",
                storage_state_file=data_dir / f"{normalized_platform}-storage-state.json",
            )
        return AuthStatePaths(
            user_data_dir=data_dir / f"{normalized_platform}-{normalized_account_key}-user-data",
            storage_state_file=data_dir / f"{normalized_platform}-{normalized_account_key}-storage-state.json",
        )

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        value = str(platform or "").strip().lower()
        if not value:
            raise ValueError("platform is required")
        return value

    @staticmethod
    def _normalize_account_key(account_key: str) -> str:
        value = str(account_key or "").strip().lower()
        if not value:
            return "default"
        value = re.sub(r"[^a-z0-9-]+", "-", value)
        value = re.sub(r"-{2,}", "-", value).strip("-")
        return value or "default"
