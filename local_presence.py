"""Local presence detection for Windows.

Derives presence from signals already tracked by Windows, with no
authentication required:

  * Capability Access Manager registry entries record which apps are
    currently using the microphone, webcam, and screen capture. A
    LastUsedTimeStop value of 0 means the capability is in use right now.
  * Visible window titles catch screen sharing, which Teams does not report
    to the Capability Access Manager at all - see is_screen_sharing().
  * GetLastInputInfo gives keyboard/mouse idle time for AWAY detection.
  * Process enumeration tells us whether Teams is running at all.
"""

import ctypes
import winreg
from ctypes import wintypes

from config import (
    BROWSER_EXE_APPS,
    IDLE_THRESHOLD,
    INCLUDE_BROWSERS,
    MONITORED_EXE_APPS,
    MONITORED_PACKAGED_APPS,
    SCREEN_SHARE_WINDOW_TITLES,
    TEAMS_PROCESS_NAMES,
)

CONSENT_STORE = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion"
    r"\CapabilityAccessManager\ConsentStore"
)

MICROPHONE = "microphone"
WEBCAM = "webcam"
SCREEN_CAPTURE = "graphicsCaptureWithoutBorder"

# Non-packaged app keys store the exe path with '#' where a '\' would be.
_PATH_SEPARATOR = "#"


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def get_idle_seconds():
    """Seconds since the last keyboard or mouse input."""
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0

    # GetTickCount64 avoids the 49.7 day wraparound of GetTickCount.
    ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    uptime_ms = ctypes.windll.kernel32.GetTickCount64()
    return max(0.0, (uptime_ms - info.dwTime) / 1000.0)


def _matches_monitored_app(key_name, exe_names):
    """True if a consent store subkey belongs to one of the given apps."""
    if key_name in MONITORED_PACKAGED_APPS:
        return True
    tail = key_name.rsplit(_PATH_SEPARATOR, 1)[-1]
    return tail.lower() in {name.lower() for name in exe_names}


def _subkey_in_use(root, subkey_name):
    """True if this app's LastUsedTimeStop is 0, meaning still in use."""
    try:
        with winreg.OpenKey(root, subkey_name) as key:
            stop, _ = winreg.QueryValueEx(key, "LastUsedTimeStop")
            return stop == 0
    except (FileNotFoundError, OSError):
        return False


def is_capability_in_use(capability):
    """True if any monitored app currently holds the given capability."""
    exe_names = list(MONITORED_EXE_APPS)
    if INCLUDE_BROWSERS:
        exe_names.extend(BROWSER_EXE_APPS)

    path = f"{CONSENT_STORE}\\{capability}"
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
    except (FileNotFoundError, OSError):
        return False

    with root:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1

            if name == "NonPackaged":
                if _nonpackaged_in_use(root, exe_names):
                    return True
                continue

            if _matches_monitored_app(name, exe_names) and _subkey_in_use(root, name):
                return True

    return False


def _nonpackaged_in_use(root, exe_names):
    """Scan the NonPackaged subtree for an in-use monitored executable."""
    try:
        nonpackaged = winreg.OpenKey(root, "NonPackaged")
    except (FileNotFoundError, OSError):
        return False

    with nonpackaged:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(nonpackaged, index)
            except OSError:
                break
            index += 1

            if _matches_monitored_app(name, exe_names) and _subkey_in_use(nonpackaged, name):
                return True

    return False


def visible_window_titles():
    """Titles of every visible top-level window."""
    titles = []
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                titles.append(buffer.value)
        return True

    # Keep a reference to the thunk for the duration of the call, or CPython
    # may collect it while EnumWindows is still invoking it.
    thunk = callback_type(callback)
    user32.EnumWindows(thunk, 0)
    return titles


def is_screen_sharing():
    """True if a screen-share indicator window is currently on screen.

    Teams does not register screen capture with the Capability Access Manager
    - its graphicsCaptureWithoutBorder entry goes stale for months and
    graphicsCaptureProgrammatic stays empty - so the registry can never see a
    share. It does open a floating "Sharing control bar | Microsoft Teams"
    window for exactly the duration of the share and close it the moment
    sharing stops, which is a dependable stand-in.

    Titles are localised, so the markers live in config.
    """
    if not SCREEN_SHARE_WINDOW_TITLES:
        return False

    markers = [marker.lower() for marker in SCREEN_SHARE_WINDOW_TITLES]
    for title in visible_window_titles():
        lowered = title.lower()
        if any(marker in lowered for marker in markers):
            return True
    return False


def is_teams_running():
    """True if a Teams process is currently running."""
    try:
        import psutil
    except ImportError:
        # Without psutil we cannot tell; assume running so we do not
        # incorrectly report OFFLINE.
        return True

    wanted = {name.lower() for name in TEAMS_PROCESS_NAMES}
    for process in psutil.process_iter(["name"]):
        name = process.info.get("name")
        if name and name.lower() in wanted:
            return True
    return False


def get_presence():
    """Derive a presence state from local signals.

    Returns the same shape as teams_presence.get_presence() so either
    source can drive the display pipeline.
    """
    mic = is_capability_in_use(MICROPHONE)
    camera = is_capability_in_use(WEBCAM)

    # Check the registry first - Zoom and browsers do register screen capture
    # - then fall back to the indicator window, which is what catches Teams.
    presenting = is_capability_in_use(SCREEN_CAPTURE) or is_screen_sharing()

    idle = get_idle_seconds()

    # Enumerating processes is the most expensive signal here, so read it once.
    teams = is_teams_running()

    if presenting:
        availability = "Presenting"
    elif mic and camera:
        availability = "InAVideoCall"
    elif mic:
        availability = "InACall"
    elif not teams:
        availability = "Offline"
    elif idle >= IDLE_THRESHOLD:
        availability = "Away"
    else:
        availability = "Available"

    return {
        "availability": availability,
        "activity": availability,
        "status_message": None,
        "signals": {
            "microphone": mic,
            "webcam": camera,
            "screen_capture": presenting,
            "idle_seconds": round(idle),
            "teams_running": teams,
        },
    }