"""Version metadata service.

Reads `VERSION` file at the runtime root if present; falls back to
`git rev-parse --short HEAD` in development; finally returns sentinel
``dev-unknown`` so callers can always render version information.

See ``docs/specs/50-system-and-ops.md`` REQ-SYS-001 / REQ-SYS-002.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.runtime_paths import get_runtime_paths


_PROCESS_STARTED_AT_MONO: float = time.monotonic()
_PROCESS_STARTED_AT: datetime = datetime.now(timezone.utc)


@dataclass(slots=True)
class VersionInfo:
    version: str = "dev-unknown"
    commit: str = "unknown"
    built_at: str = ""
    channel: str = "dev"
    python_version: str = field(default_factory=lambda: platform.python_version())
    runtime_root: str = ""
    started_at: str = ""
    uptime_seconds: float = 0.0


def _parse_version_file(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip().lower()] = value.strip()
    return values


def _read_version_file() -> dict[str, str]:
    paths = get_runtime_paths()
    candidates = [paths.runtime_root / "VERSION"]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "VERSION")
    for candidate in candidates:
        if candidate.exists():
            try:
                return _parse_version_file(candidate.read_text(encoding="utf-8-sig"))
            except OSError:
                continue
    return {}


def _git_short_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=str(get_runtime_paths().runtime_root),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_version_info() -> VersionInfo:
    paths = get_runtime_paths()
    file_values = _read_version_file()

    version = file_values.get("version") or "dev-unknown"
    commit = file_values.get("commit") or ""
    built_at = file_values.get("built_at") or ""
    channel = file_values.get("channel") or "dev"

    if not commit or commit == "unknown":
        git_commit = _git_short_commit()
        if git_commit:
            commit = git_commit
    if not commit:
        commit = "unknown"

    return VersionInfo(
        version=version,
        commit=commit,
        built_at=built_at,
        channel=channel,
        python_version=platform.python_version(),
        runtime_root=str(paths.runtime_root),
        started_at=_PROCESS_STARTED_AT.isoformat(),
        uptime_seconds=round(max(0.0, time.monotonic() - _PROCESS_STARTED_AT_MONO), 3),
    )
