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
    """Local-LAN control via tinytuya. Needs device_id, local_key, and IP."""

    def __init__(self, device_id: str, local_key: str, ip: str, version: str = "3.3"):
        import tinytuya  # imported lazily so FakeDriver users need no dep

        self._device = tinytuya.OutletDevice(device_id, ip, local_key)
        self._device.set_version(float(version))

    def _set(self, on: bool) -> bool:
        import tinytuya

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
            except tinytuya.TuyaException as exc:
                log.warning("Tuya command failed (attempt %d): %s", attempt, exc)
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
        for dp in status or []:
            if dp.get("dps", "1") == "1" or dp.get("code") == "switch_1":
                return bool(dp.get("value"))
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
    return TuyaDriver(cfg.device_id, cfg.local_key, cfg.ip, cfg.version)
