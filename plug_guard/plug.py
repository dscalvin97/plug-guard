"""Smart plug drivers.

TuyaDriver wraps tinytuya for local-LAN control of Tuya white-label plugs
(Wipro Next Smart Home plugs are Tuya firmware — verified via Tuya cloud API
writeups). FakeDriver is a dry-run stand-in for testing without hardware.
"""

from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class PlugDriver(Protocol):
    def turn_on(self) -> bool: ...
    def turn_off(self) -> bool: ...
    def is_on(self) -> bool | None: ...


class TuyaDriver:
    """Local-LAN control via tinytuya. Needs device_id, local_key, and the plug
    located by MAC (preferred) or a last-known IP hint."""

    def __init__(self, device_id: str, local_key: str, ip: str = "", mac: str = "",
                 subnet: str = "", version: str = "3.3"):
        import tinytuya  # imported lazily so FakeDriver users need no dep

        self._tinytuya = tinytuya
        self._device_id = device_id
        self._local_key = local_key
        self._ip_hint = ip
        self._mac = mac
        self._subnet = subnet
        self._version = float(version)
        self.ip = self._locate()
        self._device = self._connect()

    def _locate(self) -> str:
        from .discover import resolve_ip

        if self._mac:
            found = resolve_ip(self._mac, hint_ip=self._ip_hint or None,
                               subnet_prefix=self._subnet or None)
            if found:
                log.info("Plug located at %s (MAC %s)", found, self._mac)
                return found
            if self._ip_hint:
                log.warning("MAC scan missed plug, falling back to hint IP %s", self._ip_hint)
                return self._ip_hint
            raise RuntimeError(f"Plug with MAC {self._mac} not found on LAN")
        return self._ip_hint

    def _connect(self):
        device = self._tinytuya.OutletDevice(self._device_id, self.ip, self._local_key)
        device.set_version(self._version)
        return device

    def _reconnect(self) -> None:
        """Re-locate the plug (DHCP may have moved it) and rebuild the handle."""
        self.ip = self._locate()
        self._device = self._connect()

    def _set(self, on: bool) -> bool:
        for attempt in (1, 2):
            try:
                if on:
                    self._device.turn_on()
                else:
                    self._device.turn_off()
                state = self.is_on()
                if state is on:
                    return True
                log.warning("Plug command not confirmed (attempt %d)", attempt)
            except self._tinytuya.TuyaException as exc:
                log.warning("Tuya command failed (attempt %d): %s", attempt, exc)
            if self._mac and attempt == 1:
                try:  # DHCP may have moved the plug — re-locate and retry once
                    self._reconnect()
                except RuntimeError as exc:
                    log.error("Re-discovery failed: %s", exc)
        return False

    def turn_on(self) -> bool:
        return self._set(True)

    def turn_off(self) -> bool:
        return self._set(False)

    def is_on(self) -> bool | None:
        try:
            status = self._device.status()
        except Exception as exc:  # tinytuya raises TuyaException and assorted socket errors
            log.warning("Plug status query failed: %s", exc)
            return None
        if not isinstance(status, dict):
            return None
        dps = status.get("dps") or {}
        # single-switch plugs use dps "1"; power strips use "switch_1" style codes
        for key in ("1", "switch_1"):
            if key in dps:
                return bool(dps[key])
        return None


class FakeDriver:
    """Dry-run driver: logs what it would do, never touches hardware."""

    def __init__(self) -> None:
        self._state = False

    def turn_on(self) -> bool:
        self._state = True
        log.info("[fake plug] turned ON")
        return True

    def turn_off(self) -> bool:
        self._state = False
        log.info("[fake plug] turned OFF")
        return True

    def is_on(self) -> bool | None:
        return self._state


class InteropDriver:
    """Hybrid driver for WSL when the plug sits on the Windows Mobile Hotspot.

    WSL's virtual network stack cannot reach a hotspot subnet (the hotspot's
    virtual adapter is not mirrored into WSL), but a Windows process launched
    via WSL interop can. So discovery stays in WSL (Windows maintains a static
    ARP entry that tracks the plug's current IP), while the actual tinytuya
    command is delegated to a small Windows-side Python script (plugctl.py).
    """

    def __init__(self, device_id: str, local_key: str, ip: str = "", mac: str = "",
                 subnet: str = "", version: str = "3.3", python_path: str = "",
                 script_path: str = ""):
        self._device_id = device_id
        self._local_key = local_key
        self._mac = mac
        self._subnet = subnet
        self._version = version
        self._python = python_path
        self._script = script_path
        self._ip_hint = ip
        self.ip = self._locate()

    def _locate(self) -> str:
        from .discover import resolve_ip

        if self._mac:
            found = resolve_ip(self._mac, hint_ip=self._ip_hint or None,
                               subnet_prefix=self._subnet or None)
            if found:
                log.info("Plug located at %s (MAC %s, via WSL ARP)", found, self._mac)
                return found
            if self._ip_hint:
                log.warning("MAC scan missed plug, falling back to hint IP %s", self._ip_hint)
                return self._ip_hint
            raise RuntimeError(f"Plug with MAC {self._mac} not found on LAN")
        return self._ip_hint

    def _call(self, action: str) -> dict:
        import json
        import subprocess

        req = json.dumps({
            "action": action,
            "device_id": self._device_id,
            "local_key": self._local_key,
            "ip": self.ip,
            "version": self._version,
        })
        try:
            # Linux must open the exe to spawn it (needs /mnt/c/... form), but the
            # script arg stays Windows-style because Windows Python reads argv as
            # Windows paths. Config stores both Windows-style; convert exe only.
            exe = self._python
            if len(exe) > 2 and exe[1] == ":":
                exe = "/mnt/" + exe[0].lower() + exe[2:].replace("\\", "/")
            # plugctl.py sets an 8s tinytuya socket timeout, so a healthy call
            # returns well inside this; keep headroom but don't stall the tick.
            res = subprocess.run(
                [exe, self._script],
                input=req, capture_output=True, text=True, timeout=20,
            )
            lines = [ln for ln in res.stdout.strip().splitlines() if ln.strip()]
            if not lines:
                log.warning("interop produced no output (rc=%s): %s", res.returncode, res.stderr.strip())
                return {"ok": False, "error": f"no output, rc={res.returncode}"}
            return json.loads(lines[-1])
        except Exception as exc:
            log.warning("interop call failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _relocate(self) -> None:
        """Re-locate the plug (hotspot DHCP may have moved it)."""
        self.ip = self._locate()

    def _set(self, on: bool) -> bool:
        for attempt in (1, 2):
            r = self._call("on" if on else "off")
            if r.get("ok") and r.get("on") is on:
                return True
            log.warning("interop turn_%s not confirmed (attempt %d): %s",
                        "on" if on else "off", attempt, r.get("error"))
            if attempt == 1:
                try:
                    self._relocate()
                except RuntimeError as exc:
                    log.error("Re-discovery failed: %s", exc)
        return False

    def turn_on(self) -> bool:
        return self._set(True)

    def turn_off(self) -> bool:
        return self._set(False)

    def is_on(self) -> bool | None:
        r = self._call("status")
        if r.get("ok"):
            return r.get("on")
        return None


def build_driver(cfg) -> PlugDriver:
    if cfg.dry_run:
        return FakeDriver()
    if getattr(cfg, "interop_python", ""):
        return InteropDriver(cfg.device_id, cfg.local_key, ip=cfg.ip, mac=cfg.mac,
                             subnet=cfg.subnet, version=cfg.version,
                             python_path=cfg.interop_python,
                             script_path=cfg.interop_script)
    return TuyaDriver(cfg.device_id, cfg.local_key, ip=cfg.ip, mac=cfg.mac,
                      subnet=cfg.subnet, version=cfg.version)
