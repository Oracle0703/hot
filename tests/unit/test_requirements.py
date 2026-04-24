from __future__ import annotations

from pathlib import Path


def test_requirements_include_pywin32_for_windows_portalocker() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "pywin32" in requirements


def test_pyinstaller_spec_includes_pywin32_runtime_dependencies() -> None:
    spec_text = Path("hot_collector.spec").read_text(encoding="utf-8")

    assert "pythoncom" in spec_text
    assert "pywintypes" in spec_text
    assert 'collect_data_files("pywin32_system32")' in spec_text
