"""CLI entry point: `plug-guard` (tray app) or `plug-guard status` (one-shot)."""

from __future__ import annotations

import argparse
import logging
import sys

from .battery import read_battery
from .config import Config


def main() -> None:
    parser = argparse.ArgumentParser(prog="plug-guard",
                                     description="Switch a smart plug based on laptop battery state")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--dry-run", action="store_true", help="never touch the real plug")
    parser.add_argument("--no-tray", action="store_true",
                        help="run headless (no system tray icon; for systemd/WSL)")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("status", help="print battery + config and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.dry_run:
        import os

        os.environ["PLUGGUARD_DRY_RUN"] = "1"
    cfg = Config.load()

    if args.cmd == "status":
        battery = read_battery()
        print(f"battery: {battery.percent}% status={battery.status} ac_online={battery.ac_online}")
        print(f"plug: device_id={cfg.device_id or '(dry-run)'} ip={cfg.ip} "
              f"thresholds: on<={cfg.turn_on_below}% off>={cfg.turn_off_above}%")
        sys.exit(0)

    from .tray import App

    app = App(cfg)
    if args.no_tray:
        app.run_headless()
    else:
        app.run()


if __name__ == "__main__":
    main()
