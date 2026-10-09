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

2. **Get the Tuya local key** (once):

   ```sh
   pipx install tinytuya   # or: pip install tinytuya
   python -m tinytuya wizard
   ```

   Sign in with the same account as the app; the wizard prints `device_id`,
   `local_key`, and lets you pick the device IP. Give the plug a **DHCP
   reservation** on your router so the IP doesn't drift.

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
     "ip": "192.168.1.50",
     "turn_on_below": 20,
     "turn_off_above": 90,
     "poll_interval": 60
   }
   ```

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
  WSL kernel ≥ 5.10 (default on current Windows 11).
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
