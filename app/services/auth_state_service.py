from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.runtime_paths import detect_runtime_root


@dataclass(slots=True)
class AuthStatePaths:
    user_data_dir: Path
    storage_state_file: Path


class AuthStateService:
    def __init__(self, runtime_root: str | Path | None = None) -> None:
        self.runtime_root = detect_runtime_root(runtime_root)

    def build_paths(self, platform: str) -> AuthStatePaths:
        normalized_platform = self._normalize_platform(platform)
        data_dir = self.runtime_root / "data"
        return AuthStatePaths(
            user_data_dir=data_dir / f"{normalized_platform}-user-data",
            storage_state_file=data_dir / f"{normalized_platform}-storage-state.json",
        )

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        value = str(platform or "").strip().lower()
        if not value:
            raise ValueError("platform is required")
        return value
