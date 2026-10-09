"""System tray UI (pystray) + the polling loop behind it."""

from __future__ import annotations

import logging
import threading

import pystray
from PIL import Image, ImageDraw

from .battery import BatteryState, read_battery
from .config import Config
from .controller import Controller
from .plug import PlugDriver, build_driver

log = logging.getLogger(__name__)


def _icon_image(color: str) -> Image.Image:
    """Draw a simple plug glyph so we ship no binary assets."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([18, 26, 46, 58], radius=6, fill=color)
    d.rectangle([26, 10, 30, 28], fill=color)
    d.rectangle([34, 10, 38, 28], fill=color)
    return img


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.controller = Controller(cfg.turn_on_below, cfg.turn_off_above)
        self.plug: PlugDriver = build_driver(cfg)
        self.battery: BatteryState | None = None
        self.plug_on: bool | None = None
        self.paused = False
        self._stop = threading.Event()
        self.icon = pystray.Icon(
            "plug-guard",
            icon=_icon_image("gray"),
            title="plug-guard",
            menu=pystray.Menu(
                pystray.MenuItem(lambda item: self._status_text(), None, enabled=False),
                pystray.MenuItem("Pause automation", self._toggle_paused, checked=lambda _: self.paused),
                pystray.MenuItem("Toggle plug now", self._toggle_plug_now),
                pystray.MenuItem("Quit", self._quit),
            ),
        )

    # ---- menu callbacks (run on the icon thread) ----

    def _status_text(self) -> str:
        if self.battery is None:
            return "Battery: reading…"
        b = self.battery
        pct = f"{b.percent}%" if b.percent is not None else "?%"
        return f"Bat {pct} ({b.status}) | plug {'ON' if self.plug_on else 'OFF' if self.plug_on is False else '?'}"

    def _toggle_paused(self, _icon, _item) -> None:
        self.paused = not self.paused
        log.info("Automation %s", "paused" if self.paused else "resumed")

    def _toggle_plug_now(self, _icon, _item) -> None:
        threading.Thread(target=self._manual_toggle, daemon=True).start()

    def _manual_toggle(self) -> None:
        target = not bool(self.plug_on)
        ok = self.plug.turn_on() if target else self.plug.turn_off()
        self.plug_on = target if ok else self.plug.is_on()
        log.info("Manual toggle %s", "succeeded" if ok else "FAILED")

    def _quit(self, _icon, _item) -> None:
        self._stop.set()
        self.icon.stop()

    # ---- worker loop ----

    def _tick(self) -> None:
        try:
            battery = read_battery()
        except RuntimeError as exc:
            log.error("Battery read failed: %s", exc)
            return
        self.battery = battery

        if self.paused:
            self.plug_on = self.plug.is_on()
            return

        decision = self.controller.decide(battery)
        log.info("Battery %s%% (%s, AC=%s) -> %s",
                 battery.percent, battery.status, battery.ac_online, decision.reason)

        current = self.plug.is_on()
        self.plug_on = current
        if decision.turn_on is None or current is decision.turn_on:
            return
        ok = self.plug.turn_on() if decision.turn_on else self.plug.turn_off()
        self.plug_on = decision.turn_on if ok else self.plug.is_on()
        log.info("Plug turned %s (%s)", "ON" if decision.turn_on else "OFF",
                 "confirmed" if ok else "NOT confirmed")

    def _run_loop(self) -> None:
        while not self._stop.wait(self.cfg.poll_interval):
            self._tick()
            self.icon.icon = _icon_image(
                "#2ecc71" if self.plug_on else "#e74c3c" if self.plug_on is False else "gray"
            )
            self.icon.title = self._status_text()

    def run(self) -> None:
        self._tick()  # one synchronous tick before showing the icon
        threading.Thread(target=self._run_loop, daemon=True).start()
        self.icon.run()
