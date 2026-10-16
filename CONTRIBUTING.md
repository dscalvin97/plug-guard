# Contributing

Thanks for helping. plug-guard is small on purpose — keep it that way.

## Dev setup

```sh
git clone https://github.com/dscalvin97/plug-guard.git
cd plug-guard
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"     # Windows: .venv\Scripts\pip install -e ".[dev]"
```

## Run the tests

```sh
.venv/bin/pytest          # Windows: .venv\Scripts\pytest
```

The suite needs no hardware and no network:

- `tests/test_controller.py` — hysteresis, edge thresholds, unknown-percent
  handling against the pure `Controller.decide`.
- `tests/test_battery.py` — `read_sysfs` against a fake `/sys/class/power_supply`
  tree built in `tmp_path`.
- `tests/test_discover.py` — `find_ip_by_mac` / `_norm_mac` against canned
  `arp -a` (Windows) and `ip neigh` (Linux) output. Use RFC 5737 TEST-NET
  addresses (`192.0.2.x`) and placeholder MACs in fixtures — never real ones.

Manual checks (real hardware): `plug-guard status`, `plug-guard --dry-run`,
then the tray app.

## Code style

- **Standard library first.** The only runtime deps are tinytuya, pystray and
  Pillow. Don't add a dependency for what the stdlib can do.
- **Lazy imports at the edges.** Modules that a headless run must not touch
  (pystray/PIL → Xlib) are imported inside the function that needs them, not
  at module top. Keep it that way — top-level `import pystray` breaks
  `--no-tray` on machines without a display.
- `logging`, not `print` (except the CLI `status` output).
- Dataclasses for data (`BatteryState`, `Decision`, `Config`); type hints
  throughout; the driver interface is the `PlugDriver` protocol.
- The controller must stay a pure function of `(battery snapshot,
  thresholds)` — that's what makes it testable without hardware.

## PR expectations

- Behavior changes come with a test. Pure-logic changes (controller,
  discovery parsing, config) should be covered in the existing style.
- No secrets, ever — no real keys, device IDs, IPs or MACs in code, tests, or
  docs. Placeholders only (`bfxxxxxxxxxxxxxxxx`, `aa:bb:cc:dd:ee:ff`,
  `192.0.2.x` in test fixtures).
- Keep the README honest: if you change a flag, config field, path, or
  default, update `README.md` (and `ARCHITECTURE.md` if it's structural).
- Small, focused PRs. If you're unsure whether a feature belongs here, open
  an issue first — plug-guard deliberately does one thing.
