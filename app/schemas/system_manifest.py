from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class NavigationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    href: str


class RuntimeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_root: str
    reports_root: str
    pid_file: str


class ServiceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_url: str
    desktop_manifest_url: str
    health_url: str
    docs_url: str


class LaunchControlManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["launcher-start"]
    launcher_path: str
    source_entry_path: str
    release_bat_path: str
    preferred_path: str
    launch_mode: Literal["batch-file", "native-executable", "python-script"]
    preferred_args: list[str]
    default_args: list[str]


class ProbeControlManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["launcher-probe"]
    script_path: str
    release_bat_path: str
    preferred_path: str
    launch_mode: Literal["batch-file", "powershell-file"]
    preferred_args: list[str]
    default_args: list[str]


class StopControlManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stop-script"]
    script_path: str
    release_bat_path: str
    preferred_path: str
    launch_mode: Literal["batch-file", "powershell-file"]
    preferred_args: list[str]
    default_args: list[str]


class ControlManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    launch: LaunchControlManifest
    probe: ProbeControlManifest
    stop: StopControlManifest


class DesktopManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["desktop-shell-manifest"]
    app_name: str
    app_env: str
    version: str
    entry_route: str
    info_route: str
    health_route: str
    docs_route: str
    navigation: list[NavigationItem]
    runtime: RuntimeManifest
    service: ServiceManifest
    control: ControlManifest
