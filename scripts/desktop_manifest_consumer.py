from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from pydantic import ValidationError

from app.schemas.system_manifest import DesktopManifest

ControlName = Literal["launch", "probe", "stop"]
SCHEMA_PATH = PROJECT_ROOT / "docs" / "specs" / "desktop-manifest.schema.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="桌面壳 manifest 最小消费示例")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--manifest-file", help="本地 manifest JSON 文件路径")
    source_group.add_argument("--manifest-url", help="manifest 接口 URL")
    parser.add_argument(
        "--control",
        choices=["launch", "probe", "stop"],
        default="probe",
        help="要解析的控制入口，默认 probe",
    )
    parser.add_argument("--print-json", action="store_true", help="输出结构化 JSON")
    return parser


def load_manifest_from_file(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_manifest_from_url(url: str) -> dict[str, object]:
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("manifest 响应不是 JSON object")
    return payload


def resolve_command(manifest: DesktopManifest, control_name: ControlName) -> list[str]:
    control = getattr(manifest.control, control_name)
    if control.launch_mode == "batch-file":
        return ["cmd.exe", "/c", control.preferred_path, *control.preferred_args]
    if control.launch_mode == "powershell-file":
        return [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            control.preferred_path,
            *control.preferred_args,
        ]
    if control.launch_mode == "python-script":
        return ["python", control.preferred_path, *control.preferred_args]
    if control.launch_mode == "native-executable":
        return [control.preferred_path, *control.preferred_args]
    raise ValueError(f"unsupported launch_mode: {control.launch_mode}")


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.manifest_file:
            raw_manifest = load_manifest_from_file(args.manifest_file)
            manifest_source = str(Path(args.manifest_file).resolve())
        else:
            raw_manifest = load_manifest_from_url(args.manifest_url)
            manifest_source = args.manifest_url

        manifest = DesktopManifest.model_validate(raw_manifest)
        control_name: ControlName = args.control
        control = getattr(manifest.control, control_name)
        payload = {
            "manifest_source": manifest_source,
            "schema_path": str(SCHEMA_PATH),
            "control": control_name,
            "preferred_path": control.preferred_path,
            "launch_mode": control.launch_mode,
            "preferred_args": control.preferred_args,
            "command": resolve_command(manifest, control_name),
        }
    except (OSError, json.JSONDecodeError, httpx.HTTPError, ValidationError, ValueError) as exc:
        print(f"DesktopManifest consumer failed: {exc}", file=sys.stderr)
        return 1

    if args.print_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(" ".join(payload["command"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
