import time

from busylib import BusyBar, types

from config import (
    APP_NAME,
    BUSY_BAR_API_TOKEN,
    BUSY_BAR_LAN_IP,
    BUSY_BAR_LAN_TOKEN,
    TRIGGER_SMART_HOME,
)
from log import log

# The device ships an "infinite" BUSY card that runs until stopped, which is
# exactly the shape we want for mirroring presence.
INFINITE_CARD_ID = "00000000-0000-0000-0000-000000000000"

# A snapshot always carries a theme, even when no session is running, so we
# need a harmless one to send when stopping. It is not displayed.
PLACEHOLDER_THEME = "on_call"

# Distinct from None, which is a real state meaning "bar is idle".
_UNSET = object()


class BusyBarDisplay:
    def __init__(self):
        self._client = None
        self._using_lan = True
        self._current_theme = _UNSET

    def connect(self):
        if BUSY_BAR_LAN_TOKEN:
            try:
                client = BusyBar(BUSY_BAR_LAN_IP, token=BUSY_BAR_LAN_TOKEN)
                # /api/version is unauthenticated, so it only proves reachability.
                # status_device() is gated, so it also proves the token is valid.
                client.version()
                client.status_device()
                self._client = client
                self._using_lan = True
                log(f"Connected to BUSY Bar over LAN ({BUSY_BAR_LAN_IP})")
                return
            except Exception as e:
                log(f"LAN connection failed: {e}")

        if BUSY_BAR_API_TOKEN:
            try:
                client = BusyBar(token=BUSY_BAR_API_TOKEN)
                client.version()
                client.status_device()
                self._client = client
                self._using_lan = False
                log("Connected to BUSY Bar over internet API")
                return
            except Exception as e:
                log(f"Internet connection failed: {e}")

        raise ConnectionError("Could not connect to BUSY Bar via LAN or internet.")

    def set_theme(self, theme):
        """Show one of the bar's built-in themes, or None to return it to idle.

        Driving the device's native BUSY session means the bar genuinely *is*
        busy rather than merely looking it: the state shows in the BUSY app,
        survives this script exiting, and can drive smart-home lights.

        The same artwork can also be painted directly with
        AnimationElement(stock_path=...), but that only sets pixels and leaves
        the device's own status untouched. See DEVICE_NOTES.md.
        """
        if not self._client:
            self.connect()

        # Re-sending the same theme restarts its animation, so only push on
        # change and let a running animation play through.
        if theme == self._current_theme:
            return

        try:
            self._apply(theme)
        except Exception as e:
            log(f"Display update failed: {e}")
            self._client = None
            self.connect()
            self._apply(theme)

        self._current_theme = theme
        log(f"bar: {theme or 'idle'}")

    def _apply(self, theme):
        settings = types.BusyBarSettings(
            theme=theme or PLACEHOLDER_THEME,
            show_work_phase_only=False,
            trigger_smart_home=TRIGGER_SMART_HOME,
        )

        if theme is None:
            snapshot = types.BusySnapshotNotStarted(
                type="NOT_STARTED",
                busy_bar_settings=settings,
            )
        else:
            snapshot = types.BusySnapshotInfinite(
                type="INFINITE",
                card_id=INFINITE_CARD_ID,
                is_paused=False,
                busy_bar_settings=settings,
            )

        self._client.busy_snapshot_set(
            types.BusySnapshot(
                snapshot=snapshot,
                snapshot_timestamp_ms=int(time.time() * 1000),
            )
        )

    def clear_display(self):
        if not self._client:
            return
        try:
            self._apply(None)
            self._current_theme = None
            # Also drop any elements an earlier text-based run left behind.
            self._client.display_clear(application_name=APP_NAME)
            log("Bar returned to idle.")
        except Exception:
            pass

    @property
    def connection_type(self):
        return "LAN" if self._using_lan else "Internet"