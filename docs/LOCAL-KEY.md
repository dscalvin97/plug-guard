# Getting the Tuya local key

The **local key** is a 16-character secret each Tuya device carries. Local
control (tinytuya, and therefore plug-guard) requires it. You extract it once
from your Tuya cloud account via a browser tool — no Tuya IoT developer
account, cloud project, or Access ID/Secret needed.

## One-time extraction (QR tool)

We use [tuya-local-key](https://github.com/vineetchoudhary/tuya-local-key),
a small local web app that piggybacks on Home Assistant's public Tuya app
registration.

```sh
git clone https://github.com/vineetchoudhary/tuya-local-key.git
cd tuya-local-key
python -m venv .venv

# Linux:
.venv/bin/pip install -r requirements.txt -r requirements-web.txt
.venv/bin/waitress-serve --listen=127.0.0.1:8000 app:app

# Windows (Git Bash):
.venv/Scripts/pip install -r requirements.txt -r requirements-web.txt
.venv/Scripts/waitress-serve --listen=127.0.0.1:8000 app:app
```

Then in a browser at **http://localhost:8000**:

1. Find your **Smart Life user code**: in the Smart Life / Wipro app →
   *Me → Settings → Account and Security → User Code*.
2. Enter the code and submit.
3. **Scan the QR code** shown on the page with the app (*+ → Scan*), then tap
   **Confirm login**. The app will say you're signing into "Home Assistant" —
   expected; the tool reuses Home Assistant's public app registration.
4. Your device list loads. Find your plug and copy the **`localKey`** field.
   Also copy the **device ID** (starts with `bf`, e.g. `bfxxxxxxxxxxxxxxxx`)
   — plug-guard needs both.

## The gotcha: it is NOT hex

The key is exactly **16 characters**, but they can be any latin1 characters —
letters, digits, **and symbols**. tinytuya simply does
`local_key.encode("latin1")`; nothing is decoded as hex. So a key like
`aB3$xK9!mNpQ2rS1` is perfectly valid.

Copy it with the tool's copy button — hand-selecting in the browser often
grabs an extra character or drops a trailing symbol, and the plug will then
reject every command. Paste it into `config.json` as-is:

```json
"local_key": "your-16-char-local-key"
```

If commands fail with an auth error (`904` / "Unable to connect", or tinytuya
payload errors), suspect a mangled key before suspecting the network.

## Warning: re-pairing rotates the key

The local key is generated when the device is **paired to your account**. Any
of the following makes the old key permanently invalid:

- factory-resetting the plug,
- removing it from the Smart Life / Wipro app and re-adding it,
- re-pairing it to a different WiFi network (including moving it onto a
  hotspot).

Symptoms after rotation: every command fails (typically Tuya error **904** or
connection/auth failures from tinytuya). Fix: re-run the QR tool above, copy
the new `localKey`, and update `config.json` (plus the Windows-side
`plugctl.py` caller inherits it automatically — it receives the key over stdin
from `config.json`, no separate copy to update).

## Handling the key safely

- It's a **symmetric secret**: anyone with the key and your LAN can switch the
  plug. Treat `config.json` like a password file.
- `config.json` is gitignored — keep it that way, and never paste the key into
  issues, screenshots, or commits.
- You can also supply it via the `PLUGGUARD_LOCAL_KEY` environment variable
  instead of the file.
