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
            data = json.loads(path.read_text())
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
        if not cfg.dry_run and not (cfg.device_id and cfg.local_key and (cfg.mac or cfg.ip)):
            raise SystemExit(
                f"Missing plug config. Fill in {path} (device_id, local_key, and mac "
                "[preferred] or ip) — get the local_key via the tuya-local-key QR tool "
                "(https://github.com/vineetchoudhary/tuya-local-key, no developer account "
                "needed), or set PLUGGUARD_DRY_RUN=1."
            )
        return cfg
