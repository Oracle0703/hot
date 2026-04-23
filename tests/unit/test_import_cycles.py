from __future__ import annotations

import subprocess
import sys


def test_importing_routes_pages_does_not_trigger_circular_import() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import app.api.routes_pages"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
