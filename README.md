# plug-guard

Desktop tray app that switches a **Wipro 10A smart plug** (Tuya white-label) on when
your laptop needs charging and off once it's done — so you can leave the charger
plugged in permanently without worrying about battery health.

```
battery <= 20% & unplugged  →  plug ON   (charger gets power, laptop starts charging)
battery >= 90%              →  plug OFF  (charging complete, cut power)
```

The dead band between 20% and 90% is deliberate hysteresis — no relay flapping.

## How it talks to the plug

Wipro's Next Smart Home plugs are Tuya firmware (confirmed: Tuya IoT backend,
works with the Smart Life app). plug-guard uses
[tinytuya](https://github.com/jasonacox/tinytuya) to control the plug **over
local LAN** — no cloud calls at runtime, no hub, works with internet down.

## Setup

1. **Pair the plug** with the Wipro Next Smart Home / Smart Life app (once).

2. **Get the Tuya local key** (once, no developer account needed):

   ```sh
   git clone https://github.com/vineetchoudhary/tuya-local-key.git
   cd tuya-local-key && ./setup.sh
   .venv/bin/python -m pip install -r requirements-web.txt
   .venv/bin/waitress-serve --listen=127.0.0.1:8765 app:app
   ```

   Open `http://localhost:8765`, enter your Smart Life **user code**
   (app → Me → Settings → Account and Security → User Code), scan the QR with
   the Smart Life/Wipro app, confirm login. Your plug's `local_key` is shown
   with a copy button. Uses Tuya's official device-sharing SDK via Home
   Assistant's public app registration — **no Tuya IoT developer account,
   cloud project, or Access ID/Secret required.**

   This tool reports your key in raw latin1, not hex. Local keys are exactly
   **16 characters** but may contain any latin1 character — do not assume hex.

3. **Install plug-guard**:

   ```sh
   cd plug-guard
   python -m venv .venv && source .venv/bin/activate
   pip install -e .
   ```

4. **Configure** `~/.config/plug-guard/config.json`:

   ```json
   {
     "device_id": "bfxxxxxxxxxxxxxxxx",
     "local_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
     "mac": "80:64:7c:89:3d:a0",
     "ip": "192.168.1.70",
     "turn_on_below": 20,
     "turn_off_above": 90,
     "poll_interval": 60
   }
   ```

   `mac` is how plug-guard finds the plug — **no DHCP reservation needed.**
   `ip` is only an optional last-known hint to skip the ~5s discovery sweep.
   If the router hands the plug a new IP, plug-guard re-finds it by MAC
   automatically (and re-locates again on any command failure).

   Find your plug's MAC from the Wipro app's device info page, or your router's
   client list (it's `80:64:7c:...` for Tuya modules).

   Skip step 2-4 for a hardware-free trial: `PLUGGUARD_DRY_RUN=1`.

5. **Run**:

   ```sh
   plug-guard              # tray icon + automation
   plug-guard status       # one-shot sanity check
   plug-guard --dry-run    # automation against a fake plug
   ```

### Autostart (systemd user unit)

```ini
# ~/.config/systemd/user/plug-guard.service
[Unit]
Description=plug-guard battery-to-smartplug automation

[Service]
ExecStart=%h/.venv/bin/plug-guard
Restart=on-failure

[Install]
WantedBy=default.target
```

```sh
systemctl --user enable --now plug-guard
```

## Battery backends

- **Linux native** — sysfs (`/sys/class/power_supply`), primary.
- **WSL2** — works too: WSL passes the host battery through sysfs. Requires
  WSL kernel ≥ 5.10 (default on current Windows 11). Discovery uses an ICMP
  sweep + Windows ARP table because WSL2's NAT swallows the UDP broadcasts
  `tinytuya scan` relies on.
- **Windows native** — via `Win32_Battery` CIM, used automatically if sysfs is
  absent. Run it directly in Windows if you don't use WSL.

## Tray menu

- live status line (battery %, charge state, plug state)
- **Pause automation** — plug goes manual until resumed
- **Toggle plug now** — one-off override
- **Quit**

## Development

```sh
pip install -e ".[dev]"
pytest
```

The controller is a pure function of `(battery snapshot, thresholds)` —
tests cover hysteresis, edge thresholds, and unknown-percent handling
without touching hardware. `tests/test_battery.py` runs sysfs parsing
against a fake sysfs tree in tmp.

## Safety notes

- If the plug or battery becomes unreachable, plug-guard holds state (failsafe:
  it never blindly toggles on uncertain reads).
- The Tuya local key is a symmetric secret — keep `config.json` out of git
  (it's already gitignored) and don't screenshot the wizard output.
- This controls **mains power**. The default thresholds assume a laptop charger;
  double-check your plug's rating (10A ≈ 2300W at 230V — fine for any laptop).
