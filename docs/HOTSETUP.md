# Hotspot setup: WSL2 + Windows Mobile Hotspot

This is the hybrid topology where plug-guard runs **inside WSL2** (best
tested path, systemd for free) but the smart plug sits on the **Windows
Mobile Hotspot** instead of your home router — e.g. to keep the plug off your
main network.

```
┌─────────────────────────── your laptop ────────────────────────────┐
│                                                                    │
│  WSL2 distro                       Windows                         │
│  ┌─────────────────────┐           ┌───────────────────────────┐   │
│  │ plug-guard          │  spawns   │ plugctl.py (tinytuya)     │   │
│  │  battery ✓ (sysfs)  │─────────▶ │ reached via WSL interop   │   │
│  │  controller ✓       │  stdin/   └────────────┬──────────────┘   │
│  │  tinytuya ✗ (no route│  stdout JSON          │ LAN socket       │
│  │   to hotspot subnet) │                       ▼                  │
│  └─────────────────────┘           ┌───────────────────────────┐   │
│                                    │ Mobile Hotspot 192.168.137.x│ │
│                                    └────────────┬──────────────┘   │
└─────────────────────────────────────────────────┼──────────────────┘
                                                  ▼
                                          smart plug (Tuya)
```

## Why WSL can't just do it itself

The Mobile Hotspot runs on a Windows virtual adapter (Wi-Fi Direct), usually
the `192.168.137.x` subnet. A plug on that hotspot is only reachable from the
Windows network stack:

- **NAT mode**: WSL sits behind a virtual switch — no route to the hotspot
  subnet at all.
- **Mirrored mode does NOT fix this.** `networkingMode=mirrored` mirrors
  *physical* adapters only; the hotspot's virtual adapter is never mirrored
  into WSL. A tinytuya socket opened inside WSL still times out, even though
  Windows itself can ping the plug.

Windows processes, however, *can* be launched from WSL (WSL interop). So
plug-guard splits the job:

- **WSL** runs the app: battery reads (WSL passes the host battery through
  sysfs), the hysteresis controller, and the process that spawns the helper.
- **Windows** runs `plugctl.py` (repo root): the actual tinytuya command,
  one JSON round-trip per call.

This is `InteropDriver` in `plug_guard/plug.py`, selected automatically when
`interop_python` is set in the config.

## Prerequisites

1. **WSL2 with systemd** — `/etc/wsl.conf` inside WSL:
   ```ini
   [boot]
   systemd=true
   ```
   then `wsl --shutdown` and reopen. Set up the systemd unit as in the
   README's Linux section, including `loginctl enable-linger $USER`.
2. **A Windows Python with tinytuya** — plugctl.py runs in it:
   ```
   C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe -m pip install tinytuya
   ```
   (Any Windows Python works; note its full path.)
3. **The plug paired to the hotspot's SSID** — the hotspot must be 2.4 GHz
   (Tuya plugs can't see 5 GHz). Re-pairing **rotates the local key**; re-run
   the key extraction (`docs/LOCAL-KEY.md`) afterwards or every command fails
   with error 904.
4. **plug-guard installed inside WSL** (steps 1–4 of the README).

## Config

`~/.config/plug-guard/config.json` inside WSL — the interop fields:

```json
{
  "device_id": "bfxxxxxxxxxxxxxxxx",
  "local_key": "your-16-char-local-key",
  "mac": "aa:bb:cc:dd:ee:ff",
  "ip": "192.168.137.63",
  "interop_python": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "interop_script": "C:\\Users\\<you>\\plug-guard\\plugctl.py"
}
```

| Field | Notes |
|---|---|
| `interop_python` | Full Windows path to `python.exe` **with tinytuya installed**. Setting this switches plug-guard from `TuyaDriver` to `InteropDriver`. |
| `interop_script` | Full Windows path to `plugctl.py` from the repo root. |
| `ip` | **Load-bearing here** — see the limitation below. The plug's current hotspot IP. |
| `mac` | Still required by config validation. Recorded for completeness; in this topology WSL can't ARP the hotspot subnet, so MAC discovery can't find the plug. |

Both paths are stored **Windows-style** (`C:\...`). plug-guard converts the
python.exe path to `/mnt/c/...` form itself (Linux needs that to spawn the
exe) but passes the script argument through unchanged (Windows Python reads
argv as Windows paths). The local key travels on **stdin** as JSON, not argv,
so it never shows up in Windows process lists.

## Boot it automatically

Two pieces:

1. **The systemd unit** (runs plug-guard inside WSL at boot) — same as the
   README's Linux section: `plug-guard --no-tray`, `Restart=on-failure`,
   `systemctl --user enable --now plug-guard`, `loginctl enable-linger $USER`.
2. **Start WSL on Windows logon** — save as
   `C:\Users\<you>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\plug-guard.bat`:
   ```bat
   @echo off
   start "" wsl.exe -d <your-distro> -u <you> --exec /bin/sh -lc "systemctl --user start plug-guard.service"
   ```
   Find the distro name with `wsl -l -v`. The `-lc` (login shell) is
   **required** — without it `systemctl --user` fails silently (missing
   `DBUS_SESSION_BUS_ADDRESS`).

## Known limitation: MAC discovery falls back to the configured IP

Plug discovery works by ping-sweeping a subnet and matching the plug's MAC in
the ARP table — but the sweep runs in WSL, which cannot reach the hotspot
subnet. So the plug's MAC is (almost) never in the ARP table, discovery
misses, and `InteropDriver` falls back to the configured `ip` (it logs
`MAC scan missed plug, falling back to hint IP ...`). If no `ip` is set, the
driver refuses to start (`Plug with MAC ... not found on LAN`).

Practical consequences:

- **Pin the plug to a fixed IP on the hotspot** (Windows Mobile Hotspot
  doesn't offer DHCP reservations, but the plug tends to keep the address it
  got; check `arp -a` on the Windows side after pairing). If the hotspot hands
  the plug a new address, plug-guard's retry-after-relocate won't save you —
  re-discovery misses too — so update `ip` in `config.json` and restart the
  service.
- Verify the plug is reachable from Windows before debugging plug-guard. Run
  this from cmd/PowerShell on the Windows side (plugctl.py reads one JSON
  request from stdin):
  ```
  echo {"action":"status","device_id":"bfxxxxxxxxxxxxxxxx","local_key":"your-16-char-local-key","ip":"192.168.137.63","version":3.3} | C:\path\to\python.exe C:\Users\<you>\plug-guard\plugctl.py
  ```
  A `{"ok": true, ...}` reply means the plug side is healthy and anything
  else is plug-guard config.

## When the laptop is the thing being charged

If the controller *is* the laptop on this hotspot, the automation only runs
while that laptop is awake. It recovers after reboot (hotspot returns, plug
rejoins, plug-guard resumes), but it can't act while the laptop is fully
dead.
