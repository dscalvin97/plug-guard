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
                 version: str = "3.3"):
        import tinytuya  # imported lazily so FakeDriver users need no dep

        self._tinytuya = tinytuya
        self._device_id = device_id
        self._local_key = local_key
        self._ip_hint = ip
        self._mac = mac
        self._version = float(version)
        self.ip = self._locate()
        self._device = self._connect()

    def _locate(self) -> str:
        from .discover import resolve_ip

        if self._mac:
            found = resolve_ip(self._mac, hint_ip=self._ip_hint or None)
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


def build_driver(cfg) -> PlugDriver:
    if cfg.dry_run:
        return FakeDriver()
    return TuyaDriver(cfg.device_id, cfg.local_key, ip=cfg.ip, mac=cfg.mac, version=cfg.version)
