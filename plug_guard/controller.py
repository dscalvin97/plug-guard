"""Hysteresis controller: decides plug state from battery snapshots.

State machine (per battery snapshot):
  - plug ON  when unplugged AND percent <= turn_on_below   (needs charging)
  - plug OFF when percent >= turn_off_above               (done charging)
  - plug OFF when AC is back online and status is Full/Not charging
  - hold otherwise (no command sent)

The gap between turn_on_below and turn_off_above is deliberate hysteresis to
prevent relay flapping near a single threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .battery import BatteryState

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Decision:
    turn_on: bool | None  # None = hold current state
    reason: str


class Controller:
    def __init__(self, turn_on_below: int = 20, turn_off_above: int = 90):
        if not 0 < turn_on_below < turn_off_above <= 100:
            raise ValueError(
                f"Thresholds must satisfy 0 < on({turn_on_below}) < off({turn_off_above}) <= 100"
            )
        self.turn_on_below = turn_on_below
        self.turn_off_above = turn_off_above

    def decide(self, battery: BatteryState) -> Decision:
        if battery.percent is None:
            return Decision(None, "battery percent unknown, holding")

        if battery.percent >= self.turn_off_above:
            return Decision(False, f"{battery.percent}% >= {self.turn_off_above}% (charged)")

        if battery.ac_online or battery.charging:
            # Already receiving power; leave the plug alone unless it's full-ish
            # and we're above the on-threshold (avoid re-triggering a charge cycle).
            if battery.status in ("Full", "Not charging") and battery.percent > self.turn_on_below:
                return Decision(False, f"AC online, battery {battery.status} at {battery.percent}%")
            return Decision(None, "AC online / charging, holding")

        # Unplugged: below the on-threshold means "please charge me"
        if battery.percent <= self.turn_on_below:
            return Decision(True, f"{battery.percent}% <= {self.turn_on_below}% (needs charge)")

        return Decision(None, f"{battery.percent}% in hysteresis band, holding")
