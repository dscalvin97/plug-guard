"""Battery state detection.

Primary backend: Linux sysfs (/sys/class/power_supply) — works natively and
under WSL2 (WSL passes host battery through since kernel 5.10).

Fallback backend: Windows CIM via powershell.exe, for running plug-guard
directly on Windows (invoked automatically from WSL via /mnt/c if sysfs is
missing).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SYSFS_POWER_SUPPLY = Path("/sys/class/power_supply")


@dataclass(frozen=True)
class BatteryState:
    """A single snapshot of battery + AC state."""

    percent: int | None  # 0-100, None if unknown
    charging: bool  # actively charging right now
    ac_online: bool  # external power present
    status: str  # raw status string, e.g. "Discharging", "Full"

    @property
    def low(self) -> bool:
        return not self.ac_online


def read_sysfs(root: Path = SYSFS_POWER_SUPPLY) -> BatteryState | None:
    """Read battery state from sysfs. Returns None if no battery found."""
    if not root.is_dir():
        return None

    bat: Path | None = None
    ac_online = False
    for entry in sorted(root.iterdir()):
        type_file = entry / "type"
        if not type_file.is_file():
            continue
        try:
            dev_type = type_file.read_text().strip()
        except OSError:
            continue
        if dev_type == "Battery" and bat is None:
            bat = entry
        elif dev_type == "Mains":
            try:
                ac_online = (entry / "online").read_text().strip() == "1"
            except OSError:
                pass

    if bat is None:
        return None

    def _read(name: str) -> str | None:
        try:
            return (bat / name).read_text().strip()
        except OSError:
            return None

    status = _read("status") or "Unknown"
    capacity_raw = _read("capacity")
    percent = int(capacity_raw) if capacity_raw and capacity_raw.isdigit() else None

    charging = status == "Charging"
    # Some systems report status without a real AC flag; trust AC flag primarily.
    if status == "Discharging":
        ac_online = False
    elif status in ("Charging", "Full", "Not charging"):
        ac_online = True

    return BatteryState(percent=percent, charging=charging, ac_online=ac_online, status=status)


def read_windows() -> BatteryState | None:
    """Read battery state via Windows CIM (works from WSL via /mnt/c powershell)."""
    ps_paths = [
        Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"),
        Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"),
    ]
    ps = next((p for p in ps_paths if p.exists()), None)
    if ps is None:
        return None

    cmd = (
        "Get-CimInstance Win32_Battery | "
        "Select-Object EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            [str(ps), "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None

    if not out or "EstimatedChargeRemaining" not in out:
        return None

    import json

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        data = data[0]

    percent = data.get("EstimatedChargeRemaining")
    # Win32_Battery.BatteryStatus: 1=discharging, 2=on AC, 3=fully charged, 6/7/8/9/10=charging variants
    battery_status = data.get("BatteryStatus", 0)
    ac_online = battery_status in (2, 3) or (percent is not None and percent >= 100)
    charging = battery_status in (6, 7, 8, 9, 10)
    return BatteryState(
        percent=int(percent) if percent is not None else None,
        charging=charging,
        ac_online=ac_online,
        status="Charging" if charging else ("Full" if battery_status == 3 else "Discharging"),
    )


def read_battery() -> BatteryState:
    """Best-effort battery read across backends. Raises RuntimeError if none work."""
    state = read_sysfs()
    if state is not None:
        return state
    state = read_windows()
    if state is not None:
        return state
    raise RuntimeError(
        "No battery backend available (sysfs missing, Windows CIM unavailable). "
        "Is this a laptop, and are you running inside a VM without battery passthrough?"
    )
