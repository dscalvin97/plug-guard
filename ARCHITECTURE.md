# Architecture

plug-guard is a small poll-decide-act loop. Every `poll_interval` seconds it
reads the battery, feeds a snapshot to a pure hysteresis controller, and sends
the resulting decision to a plug driver. No cloud calls at runtime.

```
                    plug_guard/tray.py  (App._tick — the only orchestration point)
                    ┌────────────────────────────────────────────────────────┐
                    │                                                        │
 ┌──────────────┐   │   ┌───────────────┐  Decision   ┌──────────────────┐   │
 │ battery.py   │───┼──▶│ controller.py │────────────▶│ plug.py          │   │
 │ read_battery │   │   │ Controller.   │ turn_on:    │ build_driver()   │   │
 └──────────────┘   │   │ decide()      │ True/False/ │ → driver methods │   │
        │           │   └───────────────┘ None(hold)  └────────┬─────────┘   │
        │           │                                          │             │
        ▼           │                                          ▼             │
  BatteryState      │                          ┌───────────────────────────┐ │
  (percent,         │                          │ TuyaDriver  in-process    │─┘
   charging,        │                          │             tinytuya      │
   ac_online,       │                          │ InteropDriver → plugctl.py│
   status)          │                          │             (Windows exe  │
                    │                          │             via WSL interop)
                    │                          │ FakeDriver  dry-run       │
                    │                          └───────────────────────────┘
                    └────────────────────────────────────────────────────────┘
```

## Module map

| File | Responsibility |
|---|---|
| `plug_guard/__main__.py` | CLI: `plug-guard` (tray), `--no-tray` (headless), `status` (one-shot), `--dry-run`, `-v`. Loads `Config`, picks tray vs headless. |
| `plug_guard/battery.py` | `read_battery()` → `BatteryState`. Backends: `read_sysfs` (Linux + WSL2), `read_windows` (PowerShell `Win32_Battery` CIM, tried when sysfs is absent). Raises `RuntimeError` if neither works. |
| `plug_guard/controller.py` | `Controller.decide(battery) -> Decision`. Pure function of the snapshot + thresholds; no I/O. Decision is `turn_on=True` (switch on), `False` (switch off), or `None` (hold, send nothing). Constructor validates `0 < turn_on_below < turn_off_above <= 100`. |
| `plug_guard/config.py` | `Config` dataclass; JSON file at `~/.config/plug-guard/config.json` (honors `XDG_CONFIG_HOME`), `PLUGGUARD_*` env vars override. Exits with a clear error unless `dry_run` is set or `device_id` + `local_key` + (`mac` or `ip`) are present. |
| `plug_guard/discover.py` | MAC-based plug discovery: threaded ICMP sweep + ARP-table lookup (`arp -a` on Windows/WSL, `ip neigh` on native Linux). `resolve_ip()` = fast path (hint IP still owns the MAC) → sweep → `find_ip_by_mac` with optional subnet filter. |
| `plug_guard/plug.py` | The three drivers (`TuyaDriver`, `InteropDriver`, `FakeDriver`) behind a `PlugDriver` protocol (`turn_on`/`turn_off`/`is_on`), plus `build_driver(cfg)`. |
| `plug_guard/tray.py` | `App`: the polling loop and the pystray menu. pystray/PIL are imported lazily inside `_build_icon()` so headless runs never touch Xlib. |
| `plugctl.py` | Windows-side helper (repo root, not in the package). Receives a JSON request on stdin, runs one tinytuya command, prints a JSON reply. Only used by `InteropDriver`. |

## The loop (`App._tick`)

1. `read_battery()` — sysfs first, Windows CIM as fallback. On failure the tick
   aborts and the plug state is left alone (failsafe).
2. `Controller.decide(battery)` — see the state machine below.
3. `plug.is_on()` — actual current state, not a cached guess.
4. If the decision is not `None` and differs from the current state, send
   `turn_on()`/`turn_off()`. Drivers confirm by reading state back; a
   command that isn't confirmed is retried once after re-locating the plug
   (DHCP may have moved it).

Controller state machine (defaults on ≤20 / off ≥90):

- `percent >= turn_off_above` → OFF (charged).
- AC online or charging → hold, unless status is `Full`/`Not charging` and
  `percent > turn_on_below`, in which case OFF (don't re-trigger a charge
  cycle).
- Unplugged and `percent <= turn_on_below` → ON (needs charge).
- Everything else (the hysteresis band, unknown percent) → hold.

## Driver modes — when to use which

| Mode | Selected when | Reaches the plug via |
|---|---|---|
| `TuyaDriver` | default | In-process tinytuya over the local LAN. Use on native Linux, native Windows, or WSL when WSL can route to the plug's subnet (normal home-WiFi setup). |
| `InteropDriver` | `interop_python` is set in config | Delegates each tinytuya command to `plugctl.py`, spawned as a Windows process via WSL interop. Use only for the one topology where plug-guard runs in WSL2 but the plug sits on the **Windows Mobile Hotspot** (see `docs/HOTSETUP.md`). Not for native Windows/Linux — path conversion assumes WSL. |
| `FakeDriver` | `dry_run` true (or `--dry-run`) | Nothing. Logs what it would do. |

`build_driver(cfg)` picks in that order: dry-run → interop → Tuya.

## Why interop exists (WSL2 + Mobile Hotspot)

The Windows Mobile Hotspot lives on a virtual adapter (typically
`192.168.137.x`). A plug joined to that hotspot is only reachable from the
Windows network stack. WSL2 in NAT mode sits behind a virtual switch with no
route to that subnet, and **mirrored networking doesn't help**: mirrored mode
mirrors *physical* adapters only — the hotspot's Wi-Fi Direct virtual adapter
is never mirrored into WSL. So a tinytuya socket opened inside WSL always
times out, even though Windows itself can see the plug.

WSL interop, however, can launch Windows executables. So the split is:

- **WSL side** (`InteropDriver`): reads the battery, runs the controller,
  spawns the Windows Python. It passes a JSON request on stdin (which keeps
  the local key out of argv/process lists).
- **Windows side** (`plugctl.py`): owns the tinytuya socket to the plug,
  prints one JSON line back (`{"ok": true, "on": true}`).

Path handling: config stores Windows-style paths; `InteropDriver._call`
converts only the python.exe path to `/mnt/c/...` form (Linux needs that to
spawn the exe) and leaves the script argument Windows-style (Windows Python
reads argv as Windows paths).

Known limitation: plug discovery still runs in WSL, but the ICMP sweep can't
reach the hotspot subnet, so the plug's MAC is (almost) never in the ARP table
and discovery falls back to the configured `ip`. See `docs/HOTSETUP.md`.

## Discovery (MAC, no DHCP reservation)

`resolve_ip(mac, hint_ip, subnet_prefix)`:

1. Fast path — ping the hint IP; if the ARP entry for it matches the MAC,
   return it.
2. Ping-sweep the /24 (64 threads) to populate the ARP cache, then search the
   ARP dump for the MAC via `find_ip_by_mac`.
3. The subnet comes from config `subnet`, else auto-detection
   (`ipconfig` on Windows/WSL — /24 only; default-route source address on
   native Linux).

`find_ip_by_mac` accepts colon/dash/case variants of the MAC, and the optional
subnet filter drops stale cross-interface ARP entries (e.g. a home-WiFi entry
leaking into a hotspot lookup).

## Concurrency

- Tray mode: one synchronous `_tick()` before the icon appears, then a
  background worker thread runs the loop; menu callbacks run on the pystray
  icon thread and hand slow work (manual toggle) to another thread.
- Headless mode: single thread, no icon, first tick after one interval.
- `Reconnect/re-locate` happens inside the driver on command failure, not on a
  separate thread.
