"""Configuration: JSON file at ~/.config/plug-guard/config.json (see README)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "plug-guard"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class Config:
    device_id: str = ""
    local_key: str = ""
    mac: str = ""  # preferred: plug is found by MAC, survives DHCP changes
    ip: str = ""  # optional last-known hint, speeds up discovery
    subnet: str = ""  # pin discovery to a subnet, e.g. "192.168.137" (hotspot)
    interop_python: str = ""  # Windows python.exe path -> enable interop plug control
    interop_script: str = ""  # path to plugctl.py on the Windows side
    version: str = "3.3"
    turn_on_below: int = 20
    turn_off_above: int = 90
    poll_interval: int = 60  # seconds
    dry_run: bool = False

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        cfg = cls()
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"{path} is not valid JSON ({exc}). Fix the file and retry."
                )
            if not isinstance(data, dict):
                raise SystemExit(f"{path} must contain a JSON object, not {type(data).__name__}.")
            for key, value in data.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, value)
        # Env overrides beat file (useful for CI / one-off runs)
        cfg.device_id = os.environ.get("PLUGGUARD_DEVICE_ID", cfg.device_id)
        cfg.local_key = os.environ.get("PLUGGUARD_LOCAL_KEY", cfg.local_key)
        cfg.mac = os.environ.get("PLUGGUARD_MAC", cfg.mac)
        cfg.ip = os.environ.get("PLUGGUARD_IP", cfg.ip)
        cfg.subnet = os.environ.get("PLUGGUARD_SUBNET", cfg.subnet)
        cfg.interop_python = os.environ.get("PLUGGUARD_INTEROP_PYTHON", cfg.interop_python)
        cfg.interop_script = os.environ.get("PLUGGUARD_INTEROP_SCRIPT", cfg.interop_script)
        cfg.dry_run = cfg.dry_run or os.environ.get("PLUGGUARD_DRY_RUN") == "1"
        # Coerce poll_interval: a string or 0/negative here would busy-loop the
        # wait() in the run loops (Event.wait(0) returns immediately).
        try:
            cfg.poll_interval = max(1, int(cfg.poll_interval))
        except (TypeError, ValueError):
            raise SystemExit(f"poll_interval must be an integer >= 1 second, got {cfg.poll_interval!r}.")
        if not cfg.dry_run and not (cfg.device_id and cfg.local_key and (cfg.mac or cfg.ip)):
            raise SystemExit(
                f"Missing plug config. Fill in {path} (device_id, local_key, and mac "
                "[preferred] or ip) — get the local_key via the tuya-local-key QR tool "
                "(https://github.com/vineetchoudhary/tuya-local-key, no developer account "
                "needed), or set PLUGGUARD_DRY_RUN=1."
            )
        return cfg
