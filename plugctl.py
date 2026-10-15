#!/usr/bin/env python3
"""Windows-side plug control for plug-guard hybrid mode.

Runs on Windows (the only network stack that can reach a plug on the Mobile
Hotspot subnet — WSL's virtual stack cannot). Invoked from WSL via interop:
the WSL service reads the battery and makes decisions; this script performs the
actual tinytuya command and prints a JSON result.

Reads a JSON request on stdin (keeps the local_key out of argv / process lists):
    {"action": "on"|"off"|"status", "device_id": "...", "local_key": "...",
     "ip": "192.168.1.50", "version": "3.3"}
Prints one JSON line:
    {"ok": true, "on": true}   or   {"ok": false, "error": "..."}
"""
import json
import sys
import time

import tinytuya


def main() -> int:
    try:
        req = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"bad request json: {exc}"}))
        return 1

    action = req.get("action")
    ip = req.get("ip") or ""
    if action not in ("on", "off", "status") or not ip:
        print(json.dumps({"ok": False, "error": "need action on|off|status and ip"}))
        return 1

    try:
        dev = tinytuya.OutletDevice(req["device_id"], ip, req["local_key"])
        dev.set_version(float(req.get("version", "3.3")))
        dev.set_socketTimeout(8)

        if action == "on":
            dev.turn_on()
        elif action == "off":
            dev.turn_off()

        # give the relay a beat, then read back to report true state
        time.sleep(0.4)
        status = dev.status()
        dps = status.get("dps", {}) if isinstance(status, dict) else {}
        raw = dps.get("1")
        on = bool(raw) if raw is not None else None
        print(json.dumps({"ok": True, "ip": ip, "on": on}))
        return 0
    except Exception as exc:  # tinytuya raises TuyaException + assorted socket errors
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
