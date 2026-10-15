# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-13

First release: battery-driven on/off automation for a Tuya-based smart plug
(verified on a Wipro 10A plug), fully local — no cloud at runtime.

### Added

- Hysteresis controller: plug ON at ≤20% and unplugged, OFF at ≥90%; holds
  state on unknown battery readings and never blindly toggles on an uncertain
  read. (`plug_guard/controller.py`)
- Battery backends: Linux/WSL2 sysfs (`/sys/class/power_supply`) with a
  Windows CIM (`Win32_Battery` via powershell.exe) fallback for native
  Windows. (`plug_guard/battery.py`)
- MAC-based plug discovery — ICMP sweep + ARP table (`arp -a` on
  Windows/WSL, `ip neigh` on native Linux), so no DHCP reservation is needed
  and the plug is re-located automatically if its IP drifts.
  (`plug_guard/discover.py`, commit `aab70b6`)
- System tray app (pystray): live status line, Pause automation, Toggle plug
  now, Quit. Icon drawn at runtime — no binary assets. (`plug_guard/tray.py`)
- Headless mode `plug-guard --no-tray` for systemd/WSL service use, plus
  one-shot `plug-guard status`, `--dry-run` and `-v/--verbose` flags.
  (commit `6f121d8`)
- `subnet` config field to pin discovery to one /24 on multi-interface
  machines; `find_ip_by_mac` gained a subnet filter so stale cross-interface
  ARP entries can't leak through. (commit `c048d01`)
- Interop mode for the WSL2 + Windows Mobile Hotspot topology: when
  `interop_python` is set, tinytuya commands are delegated to a Windows-side
  `plugctl.py` spawned via WSL interop (WSL cannot route to the hotspot
  subnet; key passed on stdin, never argv). (`InteropDriver`,
  `plugctl.py`, commit `4a33033`)
- MIT license, README from-scratch setup guide, architecture doc,
  docs for local-key extraction and the hybrid hotspot setup.

### Fixed

- `local_key` handling: the key is any 16-char latin1 string (tinytuya does
  `encode("latin1")`), not necessarily hex. (`95a0ba5`)
- `is_on()`: tinytuya 1.20 returns `status()` as a `{'dps': {...}}` dict —
  the previous list-based parsing silently returned `None` on real hardware.
  (`95a0ba5`)
