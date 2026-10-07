# Teams Presence -> BUSY Bar

Mirrors your Microsoft Teams status onto a BUSY Bar, using the device's own
built-in status themes. Runs as a background console script on Windows.

No Azure app registration, no admin consent, no cloud account required - it
reads presence from local Windows sensors and talks to the bar over your LAN.

---

## Requirements

**Hardware**

- A BUSY Bar on the same network as this machine
- Its LAN API enabled, and the PIN from **Settings -> Developer / API**

**Software**

- **Windows** - detection uses Windows-only APIs (registry Capability Access
  Manager, `EnumWindows`, `GetLastInputInfo`). The BUSY Bar half is
  cross-platform, the presence half is not.
- **Python 3.10 or newer.** `busylib`, `requests` and `python-dotenv` all
  declare `>=3.10`. Developed and tested on 3.14.3 (64-bit).

Check yours:

    python --version

## Setup

**1. Create a virtual environment and install dependencies**

    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt

**2. Create your `.env`**

    copy .env.example .env

`.env` is gitignored and never committed - a fresh clone has no credentials,
so this step is required every time. Open it and set **at least one** token:

| Setting | What it is | Required |
|---|---|---|
| `BUSY_BAR_LAN_TOKEN` | The PIN shown on the device under Settings -> Developer / API | Yes, for LAN |
| `BUSY_BAR_API_TOKEN` | A token from your BUSY account, used only if the LAN is unreachable | Optional fallback |
| `BUSY_BAR_LAN_IP` | The bar's address (default `192.168.1.100`) | Change if yours differs |

Everything else in `.env.example` has a working default.

**3. Check detection on its own**

    .venv\Scripts\python main.py --once --verbose

This prints one reading and exits **without contacting the bar**, so you can
confirm the sensors work before involving hardware. Start a call and run it
again - `microphone` should flip to `True`.

**4. Run it**

    .venv\Scripts\python main.py

Ctrl+C stops the BUSY session and returns the bar to idle.

### Dependencies

Installed by `requirements.txt`:

| Package | Why it is needed |
|---|---|
| `busylib[media]` | Official BUSY Bar client - HTTP API, BUSY snapshots, framebuffer readback |
| `python-dotenv` | Loads `.env` so tokens stay out of the source |
| `psutil` | Process enumeration, to tell whether Teams is running at all |
| `msal` | Microsoft auth - **only** used by the Graph source, which is currently unusable (see below). Kept so `--source graph` still works if the tenant policy is ever lifted |
| `requests` | Graph HTTP calls; also a `busylib` dependency |

The registry, idle timer and window enumeration all use the standard library
(`winreg`, `ctypes`), so there is nothing else to install.

## Usage

    python main.py [--source local|graph] [--interval N] [--once] [--verbose]

| Flag | Effect |
|---|---|
| `--once` | Print a single reading and exit, without contacting the bar |
| `--verbose` | Print the raw signals on every poll |
| `--interval N` | Seconds between polls (default 5, or `POLL_INTERVAL` in `.env`) |
| `--source` | `local` (default) or `graph` |

The theme is only pushed when it changes, so a running animation is never
restarted mid-poll.

Every runtime line is timestamped, so a log read weeks later still tells you
when your status actually changed:

    Teams Presence -> BUSY Bar
    ----------------------------------
    2026-09-17 09:14:20  Presence source: local sensors (no authentication required)
    2026-09-17 09:14:21  Connected to BUSY Bar over LAN (192.168.1.100)
    2026-09-17 09:14:21  Polling every 5s. Press Ctrl+C to stop.
    2026-09-17 09:31:05  Available -> InACall
    2026-09-17 09:31:05  bar: on_call
    2026-09-17 10:02:48  InACall -> Available
    2026-09-17 10:02:48  bar: idle

The banner is deliberately left unstamped - in an appended log file it is what
marks the start of a new run.

Preview the themes on the hardware without any presence logic:

    python themes.py              # cycle through all twelve
    python themes.py on_call dnd  # just the ones you name

## Optional: start automatically at logon

Entirely optional - running `python main.py` by hand works exactly the same.
If you would rather it just be there after every logon:

    .\install-task.ps1

That registers a Scheduled Task that starts the loop when you log in. It runs
silently through `pythonw.exe` and appends to **`busy-bar.log`** in this folder,
which rotates to `busy-bar.log.old` at 1 MB. Both are gitignored.

    .\install-task.ps1 -ShowWindow   # visible console instead, for testing
    .\uninstall-task.ps1             # remove it again

**No administrator rights are needed.** The task runs as you, inside your own
session - which it must, because presence detection reads per-user registry
keys and enumerates your own windows.

Start or stop it without logging out:

    Start-ScheduledTask -TaskName "BUSY Bar Teams Presence"
    Stop-ScheduledTask  -TaskName "BUSY Bar Teams Presence"

Watch the log live:

    Get-Content busy-bar.log -Wait -Tail 20

If PowerShell refuses to run the script, allow local scripts for your user
once:

    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

<details>
<summary>Prefer to set it up by hand in Task Scheduler?</summary>

1. Open **Task Scheduler** -> **Create Task** (not *Basic* Task)
2. **General**: name it, leave *Run only when user is logged on* selected, and
   leave *Run with highest privileges* unchecked
3. **Triggers** -> New -> *At log on*, for your user
4. **Actions** -> New -> *Start a program*
   - Program: `<project>\.venv\Scripts\pythonw.exe`
   - Arguments: `"<project>\run_hidden.pyw"`
   - Start in: `<project>`
5. **Conditions**: untick *Start the task only if the computer is on AC power*
6. **Settings**: tick *If the task fails, restart every 1 minute* and untick
   *Stop the task if it runs longer than*

Point the Action at `python.exe` and `main.py` instead if you want a visible
window.

</details>

## How it detects presence

This uses **local Windows sensors**, not the Microsoft Graph API.

The original design polled Graph's `/me/presence`, which reports rich states
(`InAMeeting`, `Presenting`, `Focusing`, ...). That path is **blocked on this
tenant**: Azure app registration is denied, and device-based Conditional Access
rejects delegated sign-in with *"your admin requires the device requesting
access to be managed by &lt;your organisation&gt;."* That policy is device-scoped rather than
app-scoped, so an IT-registered app would hit the same wall unless auth ran
through the Windows broker on a managed device.

Local detection reads, in order of usefulness:

| Source | Tells us |
|---|---|
| Capability Access Manager (`HKCU` registry) | Which app holds the mic or camera *right now* |
| Visible window titles (`EnumWindows`) | Whether you are sharing your screen from Teams |
| `GetLastInputInfo` | Keyboard/mouse idle time, for AWAY |
| Process list | Whether Teams is running at all |

No tenant permission is required for any of them.

### Why screen sharing needs the window trick

Teams does **not** register screen capture with the Capability Access Manager.
Its `graphicsCaptureWithoutBorder` entry goes stale for months and
`graphicsCaptureProgrammatic` stays empty, so the registry never sees a share
- verified live, where `microphone` was the only capability held during an
active screen share.

What Teams *does* do is open a floating **`Sharing control bar | Microsoft
Teams`** window for exactly the duration of the share, and close it the moment
sharing stops. That window is the signal. (The separate "Meeting compact view"
window survives the share ending, so it is specifically the control bar that
tracks sharing.)

Window titles are localised. If your Teams UI is not in English, or you want
to cover another app, set `SCREEN_SHARE_WINDOW_TITLES` in `.env` to a
comma-separated list of substrings. Find the right one by running:

    python diagnose_share.py

Share your screen, stop, then Ctrl+C. It diffs every in-use capability, visible
window title and running process against a baseline - look for the title that
disappears when you stop sharing.

The registry is still checked first, because browsers - unlike Teams - do
register screen capture properly.

### Browser-based calls (Zoom, Meet, Teams web)

A call running in a browser tab is held by **`msedge.exe` or `chrome.exe`**,
not by the app's own executable, so it is invisible by default. Turn it on:

    INCLUDE_BROWSERS=true

This is opt-in rather than the default because it is a blunter signal: *any*
tab holding the microphone lights the bar, not just a meeting.

Native Zoom needs nothing extra - `Zoom.exe` is already in
`MONITORED_EXE_APPS`. Browser Zoom needs the setting above.

Browser screen sharing works through the registry with no window title needed,
since Edge and Chrome do register `graphicsCaptureWithoutBorder` correctly.

## How it displays

The bar ships with its own status themes - full-panel artwork with an icon,
label and animation (`ON CALL`, `MEETING`, `ON AIR`, `DO NOT DISTURB`, ...).
This app selects those rather than drawing its own text.

Themes are driven by starting a BUSY session via `PUT /api/busy/snapshot`, so
the bar genuinely *is* busy rather than merely looking it: the state shows in
the BUSY app, survives this script exiting, and can optionally drive
smart-home lights.

The same stock artwork can also be painted directly as pixels. That and other
non-obvious device behaviour is written up in
[DEVICE_NOTES.md](DEVICE_NOTES.md) - worth reading before extending this.

### What it maps

| Signal | Theme shown |
|---|---|
| Sharing your screen | `on_air` |
| Microphone + camera | `meeting` |
| Microphone only | `on_call` |
| Idle >= `IDLE_THRESHOLD` | `back_soon` |
| Teams not running | idle (session stopped) |
| otherwise | idle (session stopped) |

Sharing wins over everything else, so sharing during a video call shows
`on_air` rather than `meeting`.

"Idle" means the BUSY session is stopped and the bar returns to its normal
screen - there is no "available" theme, and a blank bar reads as *not busy*
better than a green label would.

Edit `THEME_MAP` in `config.py` to change any of this. All twelve themes:
`back_soon`, `booked`, `chill_time`, `coding`, `dnd`, `flow`, `keep_out`,
`low_social_battery`, `lunch`, `meeting`, `on_air`, `on_call`.

## Known limitations

Local sensors cannot see:

- A **scheduled meeting** vs. an ad-hoc call - both are just "mic in use", so
  both show `on_call` (or `meeting` with the camera on)
- A **manually set** Do Not Disturb / Busy / Be Right Back

Those states are mapped (`dnd`, `back_soon`, `flow`) and will light up if the
Graph source ever becomes usable.

## Connection

The bar is tried over **LAN first** (`BUSY_BAR_LAN_IP`), falling back to the
**cloud API** when the LAN is unreachable.

> **VLAN note:** if this machine sits on a different VLAN than the bar, the LAN
> leg fails with no route and the cloud token becomes the only working path.
> Check reachability with:
>
>     Test-NetConnection 192.168.1.100 -Port 80

## Smart home

Starting a BUSY session can also switch paired smart-home lights. That is off
by default; set `TRIGGER_SMART_HOME=true` in `.env` to let presence drive them.

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point and poll loop |
| `local_presence.py` | Windows sensor detection (default source) |
| `teams_presence.py` | Graph / MSAL source - retained, currently unusable |
| `busy_bar_display.py` | Drives the bar's native BUSY session |
| `config.py` | Settings and the presence -> theme map |
| `log.py` | Timestamped output helper |
| `themes.py` | Preview the built-in themes on the hardware |
| `diagnose_share.py` | Troubleshooting: diff capabilities, windows and processes |
| `run_hidden.pyw` | Silent, logged entry point used by the scheduled task |
| `install-task.ps1` / `uninstall-task.ps1` | Optional autostart at logon |
| `DEVICE_NOTES.md` | Device API findings: `stock_path`, snapshots, framebuffer |
| `.env.example` | Template for `.env`, which is gitignored |

## Re-enabling the Graph source

If the Conditional Access policy is ever lifted: register an app with the
`Presence.Read` delegated scope, set `AZURE_CLIENT_ID` and `AZURE_TENANT_ID` in
`.env`, then run with `--source graph`. `THEME_MAP` in `config.py` already
covers the richer Graph-only states (`InAMeeting`, `Focusing`, `DoNotDisturb`).