# BUSY Bar device notes

Hard-won details about the device's HTTP API that are not obvious from the
docs. Verified against API version 27.5.0.

## Drawing stock artwork: `path` vs `stock_path`

This one cost the most time, and the failure mode is misleading.

`AnimationElement` has two location fields:

| Field | Resolves against |
|---|---|
| `path` | assets **your app** uploaded via `assets_upload(application_name, ...)` |
| `stock_path` | the device's **built-in** shared assets |

Passing a built-in path to `path` does not raise. The API returns
`{"result": "OK"}` and the device draws a **magenta X** - its "asset not found"
placeholder, 16x16 in the top-left corner. Roughly 41 of 1152 pixels light up,
which is the fastest way to distinguish a placeholder from real artwork.

Wrong - renders the magenta X:

    types.AnimationElement(id="a", x=0, y=0,
        path="/ext/apps_assets/shared/animations/on_call_72x16.anim")

Right:

    types.AnimationElement(id="a", x=0, y=0,
        stock_path="/ext/apps_assets/shared/animations/on_call_72x16.anim")

`stock_path` requires the **full absolute path**. Short names (`"on_call"`,
`"on_call_72x16"`) return HTTP 400 Bad Request.

Things that were *not* the cause, despite each looking plausible at the time:
the `section` field, per-app asset namespacing, and the 255 KB `assets_upload`
size cap.

## `.anim` files are complete frames, not background layers

`theme.json` names its animation `bg_path`, which suggests a background with
the icon and label composited over it. It is not. Drawing `on_call_72x16.anim`
raw via `stock_path` produces the finished artwork - rounded red pill,
microphone icon, "ON CALL" lettering, shimmer - pixel-for-pixel identical to
what the theme renders.

## Two ways to show a status

| | `busy_snapshot_set` | `display_draw` + `stock_path` |
|---|---|---|
| Can show | the 12 themes only | any stock animation |
| Device state | a real BUSY session: visible in the BUSY app, survives your script exiting | just pixels your app owns |
| Smart home | can switch paired lights | no |
| Cleanup | set `NOT_STARTED` | `display_clear(application_name=...)` |

For presence mirroring, `busy_snapshot_set` is the right choice: you want the
device to genuinely *be* busy, not merely look it. `display_draw` is the escape
hatch for artwork that has no theme behind it.

### Starting a session

    types.BusySnapshot(
        snapshot=types.BusySnapshotInfinite(
            type="INFINITE",
            card_id="00000000-0000-0000-0000-000000000000",
            is_paused=False,
            busy_bar_settings=types.BusyBarSettings(
                theme="on_call",
                show_work_phase_only=False,
                trigger_smart_home=False,
            ),
        ),
        snapshot_timestamp_ms=int(time.time() * 1000),
    )

The all-zero `card_id` is the built-in **infinite** card, read from
`busy_profile("custom")`. The other slot, `busy_profile("busy")`, holds a
different card (`...0001`, titled "HARDCORE") that runs a 20/5-minute interval
timer rather than an open-ended session.

`BusySnapshotNotStarted` stops the session and hands the display back to the
bar's idle screen. It still requires a `theme` in `busy_bar_settings`, but the
value is not displayed.

Re-sending the same theme **restarts its intro animation**, so push only on
change. `busy_bar_display.set_theme()` guards this.

## Reading the display back

`screen("front")` returns the live framebuffer as RGB bytes - 3456 for the
front display (72x16), 38400 for the back (160x80, sent L4-packed). This is the
only trustworthy way to confirm what the bar is showing, because a successful
API response does not mean anything rendered.

Comparing two captures a second apart also reveals whether an animation is
actually running.

Useful during debugging: dump a capture to PNG at 10x scale and look at it.

## Authentication surface

`/api/version` and `/api/access` are **unauthenticated** - both return 200 with
no token at all. They prove reachability, not that your token is valid.
Validate credentials against a gated endpoint such as `status_device()`,
otherwise a wrong PIN reports a successful connection and then fails on the
first real call.

## The `.anim` container

    offset  bytes        meaning
    0x00    "bicycle0"   magic
    0x09    0x48 0x10    width 72, height 16
    0x18    uint32       section count
    0x30+   len-prefixed section names

Sections are named. `wave_invitation` carries two, `default` and `idle`; the
theme animations carry `default`. Pixel data is uncompressed RGB24.

## Themes

Twelve, each a directory under `/ext/apps_assets/busy/themes/` containing a
`theme.json` that points at its animation:

`back_soon`, `booked`, `chill_time`, `coding`, `dnd`, `flow`, `keep_out`,
`low_social_battery`, `lunch`, `meeting`, `on_air`, `on_call`

Note that `busy` appears as a theme name in the stock profiles but has **no
theme directory** - do not rely on it.

## Stock animations with no theme

These exist in `/ext/apps_assets/shared/animations/` but have no theme
directory, so they are reachable only via `stock_path`:

| File | Size | What it is |
|---|---|---|
| `wave_invitation_72x16.anim` | 110 KB | a soft grey glow swelling from the bottom of the panel and fading, pulsing. Greyscale throughout (R=G=B), no icon or text. Almost certainly the ambient backdrop for the wave-to-interact gesture. |
| `transition_select_72x16.anim` | 77 KB | UI transition |
| `start_menu_31x16.anim` | 173 KB | menu chrome |
| `spinner_back_16x16.anim` | 3.5 KB | spinner |
| `spinner_front_8x8.anim` | 3 KB | spinner |
| `calendar_event_16x16.anim` | 110 KB | calendar glyph |
| `calendar_reminder_16x16.anim` | 115 KB | calendar glyph |

## Storage

Only `/ext` paths are listable; other roots return 400 Bad Request.

`assets_upload` caps at 255 KB, which is smaller than most stock animations
(`meeting` is 1.3 MB, `chill_time` 2 MB). Copying them into your own app
namespace is therefore not viable - use `stock_path` instead.

## Network

The bar answers on port 80. If your machine is on a different VLAN, the LAN leg
fails with no route and the cloud token becomes the only working path:

    Test-NetConnection 192.168.1.100 -Port 80

For the cloud client, omit the address entirely - `BusyBar(token=...)`. Passing
a hostname like `"api.busy.app/busybar"` is parsed as a *device* address and
will not reach the cloud.