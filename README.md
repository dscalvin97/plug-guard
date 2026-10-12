# plug-guard

Keeps your laptop's battery in the 20–90% sweet spot by automatically flipping a
smart plug on and off — no cloud, no hub, all local.

Every 60 seconds it reads your battery. When you drop to ≤20% and are unplugged,
it turns the plug **on** so your charger gets power. Once you hit ≥90%, it cuts
the plug **off**. The dead band between those thresholds prevents the relay from
flapping.

It talks straight to the plug over your LAN using
[tinytuya](https://github.com/jasonacox/tinytuya) — found automatically by MAC
address, so no router configuration — and runs unattended as a background
service that survives reboots with zero interaction.

```
battery <= 20% & unplugged  →  plug ON   (charger gets power, laptop charges)
battery >= 90%              →  plug OFF  (charging complete, cut power)
```

## Supported hardware

Any Tuya-based smart plug works. Verified on a **Wipro 10A smart plug** (Tuya
white-label, firmware protocol 3.3). If your plug pairs with the Smart Life /
Tuya Smart app, plug-guard can drive it.

---

## Setup from scratch

You need: a Tuya smart plug already paired to the Smart Life / Tuya Smart (or
Wipro) app, and this repo. The one tricky part is the **local key** — a 16-char
secret the plug requires to accept local commands. You get it once, offline from
the plug, then never again.

### 1. Install prerequisites

**Linux (Debian/Ubuntu):**
```sh
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip
```

**Linux (Arch):**
```sh
sudo pacman -S git python python-pip
```

**Windows:** install [Git](https://git-scm.com/download/win) and
[Python](https://python.org/downloads) (check "Add to PATH" in the installer).
Then open **Git Bash** for the rest of the Windows steps, or use PowerShell —
both work.

### 2. Get the plug's local key (one-time)

The key comes from your Tuya account, and you can fetch it **without a Tuya
developer account** using [tuya-local-key](https://github.com/vineetchoudhary/tuya-local-key):

```sh
git clone https://github.com/vineetchoudhary/tuya-local-key.git
cd tuya-local-key
python -m venv .venv
# Linux:                              # Windows (Git Bash):
.venv/bin/pip install -r requirements.txt \
.venv/bin/pip install -r requirements-web.txt   .venv/Scripts/pip install -r requirements.txt -r requirements-web.txt
# Linux:                              # Windows:
.venv/bin/waitress-serve --listen=127.0.0.1:8000 app:app
                                     .venv/Scripts/waitress-serve --listen=127.0.0.1:8000 app:app
```

Open **http://localhost:8000** in a browser, then:

1. Find your **Smart Life user code**: in the app → *Me → Settings → Account
   and Security → User Code*.
2. Enter it, submit.
3. **Scan the QR code** with the Smart Life/Wipro app (*+ → Scan*), then tap
   **Confirm login**. It'll say you're signing into "Home Assistant" — that's
   expected; the tool reuses Home Assistant's public app registration. No
   developer account, cloud project, or Access ID/Secret involved.
4. Your device list loads — find your plug, **copy the `localKey`**.

> **On the key format:** it's exactly **16 characters**, but they can be *any*
> latin1 characters — letters, digits, **and symbols**. It is **not** always hex.
> Copy it exactly as shown (use the copy button; hand-selecting often grabs
> extra characters). A key like `aB3$xK9!mNpQ2rS1` is valid.

Grab the plug's **device ID** from the same screen (e.g. `bfxxxxxxxxxxxxxxxx`).

### 3. Install plug-guard

```sh
git clone <this-repo-url> plug-guard
cd plug-guard
# Linux: python3 -m venv .venv && .venv/bin/pip install -e .
# Windows: python -m venv .venv && .venv/Scripts/pip install -e .
```

### 4. Configure

Create `~/.config/plug-guard/config.json` (on Windows:
`C:\Users\<you>\.config\plug-guard\config.json`):

```json
{
  "device_id": "bfxxxxxxxxxxxxxxxx",
  "local_key": "your-16-char-local-key",
  "mac": "80:64:7c:xx:xx:xx",
  "ip": "192.168.1.70",
  "turn_on_below": 20,
  "turn_off_above": 90,
  "poll_interval": 60
}
```

| Field | Notes |
|---|---|
| `device_id` | From the key tool (step 2). |
| `local_key` | The 16-char key — copy exactly, symbols allowed. |
| `mac` | Plug's MAC. **This is how it's found — no DHCP reservation needed.** Tuya modules are `80:64:7c:...`. Get it from the router's client list or your plug's label. |
| `ip` | Optional last-known hint. Skips the ~5s discovery sweep. Ignored once MAC discovery runs; auto-updates if the plug moves. |
| `turn_on_below` / `turn_off_above` | Battery thresholds (%). Must satisfy `0 < on < off <= 100`. |
| `poll_interval` | Seconds between battery reads. |

### 5. Test it

```sh
# Linux:
.venv/bin/plug-guard status     # one-shot: shows battery + config, takes no action
.venv/bin/plug-guard            # tray app — watch the icon, use menu to toggle
.venv/bin/plug-guard --dry-run  # runs the logic against a fake plug (no hardware)

# Windows: swap .venv/bin/ for .venv/Scripts/
```

`status` is the sanity check — run it first. It should print your battery % and
confirm the config loaded. If it errors on missing config, step 4 is incomplete.

---

## Run it 24×7 (autostart)

### Linux (systemd)

`~/.config/systemd/user/plug-guard.service`:
```ini
[Unit]
Description=plug-guard: switch smart plug based on laptop battery
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/plug-guard/.venv/bin/plug-guard --no-tray
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```
```sh
systemctl --user daemon-reload
systemctl --user enable --now plug-guard
loginctl enable-linger $USER        # service runs even when you're not logged in
```

Manage it:
```sh
systemctl --user status plug-guard
journalctl --user -u plug-guard -f   # live log
```

### Windows via WSL2 (recommended — best tested path)

Same as Linux above, but running inside WSL. WSL passes the host battery
through sysfs, so it behaves identically. Two extra pieces make it survive a
Windows reboot:

**Enable systemd in WSL** — `C:\Users\<you>\.wslconfig` needs nothing, but
`/etc/wsl.conf` inside WSL must have:
```ini
[boot]
systemd=true
```
(Run `wsl --shutdown` and reopen to apply.) Then set up the systemd unit as
above, and enable linger: `loginctl enable-linger calvin`.

**Boot WSL on Windows logon** — save this as
`C:\Users\<you>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\plug-guard.bat`:
```bat
@echo off
start "" wsl.exe -d <your-distro> -u <you> --exec /bin/sh -lc "systemctl --user start plug-guard.service"
```
Find your distro name with `wsl -l -v`. The `-lc` (login shell) is required —
without it, `systemctl --user` fails silently (missing `DBUS_SESSION_BUS_ADDRESS`).

### Windows native

Plug-guard also runs directly on Windows (no WSL): battery via `Win32_Battery`
CIM, plug discovery via `arp -a`. Install and configure as in steps 1–4, then
run `.venv\Scripts\plug-guard.exe` for the tray app. For autostart, point a
Task Scheduler entry (at logon) at that same `.exe`. WSL2 is recommended above
because it's the most tested path and gives you systemd for free.

---

## How it talks to the plug

Wipro's Next Smart Home plugs are Tuya firmware (works with the Smart Life app).
plug-guard drives them over **local LAN** via tinytuya — no cloud calls at
runtime, no hub, works with the internet down. The plug is located by **MAC
address** (ICMP sweep + ARP table), so it survives DHCP IP changes: no router
configuration, and it re-locates automatically if the IP drifts.

## Battery backends

- **Linux native** — sysfs (`/sys/class/power_supply`).
- **WSL2** — same sysfs path (WSL passes the host battery through; needs WSL
  kernel ≥ 5.10, default on current Windows 11).
- **Windows native** — `Win32_Battery` CIM, used automatically when sysfs is
  absent.

## Tray menu

- live status line (battery %, charge state, plug state)
- **Pause automation** — plug goes manual until resumed
- **Toggle plug now** — one-off override
- **Quit**

## Config reference

All fields are optional; env vars override the file.

| Env var | Overrides |
|---|---|
| `PLUGGUARD_DEVICE_ID` | `device_id` |
| `PLUGGUARD_LOCAL_KEY` | `local_key` |
| `PLUGGUARD_MAC` | `mac` |
| `PLUGGUARD_IP` | `ip` |
| `PLUGGUARD_DRY_RUN=1` | `dry_run` (fake plug, no hardware) |

## Development

```sh
pip install -e ".[dev]"
pytest
```

The controller is a pure function of `(battery snapshot, thresholds)` — tests
cover hysteresis, edge thresholds, and unknown-percent handling without touching
hardware. `tests/test_battery.py` runs sysfs parsing against a fake tree;
`tests/test_discover.py` parses real `arp -a` / `ip neigh` output formats.

## Safety notes

- **Failsafe:** if the plug or battery is unreachable, plug-guard holds state —
  it never blindly toggles on an uncertain read.
- **The local key is a symmetric secret.** `config.json` is gitignored; don't
  screenshot the key tool.
- **This switches mains power.** Defaults assume a laptop charger. Check your
  plug's rating (10A ≈ 2300W at 230V — fine for any laptop).
