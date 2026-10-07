"""Find out which Windows signal fires when you share your screen.

Modern Teams does not register screen capture in the Capability Access
Manager, so `screen_capture` never flips and Presenting is never detected.
This watches everything at once and prints what changes, so the real signal
can be identified.

Run it, share your screen, stop sharing, then press Ctrl+C:

    python diagnose_share.py
"""

import ctypes
import time
import winreg
from ctypes import wintypes

CONSENT_STORE = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion"
    r"\CapabilityAccessManager\ConsentStore"
)


def _subkeys(key):
    names = []
    index = 0
    while True:
        try:
            names.append(winreg.EnumKey(key, index))
        except OSError:
            return names
        index += 1


def _in_use(parent, name):
    """A LastUsedTimeStop of 0 means the capability is held right now."""
    try:
        with winreg.OpenKey(parent, name) as key:
            return winreg.QueryValueEx(key, "LastUsedTimeStop")[0] == 0
    except OSError:
        return False


def capabilities_in_use():
    """Every (capability, app) pair currently marked in use."""
    found = set()
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONSENT_STORE)
    except OSError:
        return found

    with root:
        for cap in _subkeys(root):
            try:
                cap_key = winreg.OpenKey(root, cap)
            except OSError:
                continue
            with cap_key:
                for app in _subkeys(cap_key):
                    if app == "NonPackaged":
                        try:
                            np_key = winreg.OpenKey(cap_key, app)
                        except OSError:
                            continue
                        with np_key:
                            for sub in _subkeys(np_key):
                                if _in_use(np_key, sub):
                                    found.add((cap, sub))
                        continue
                    if _in_use(cap_key, app):
                        found.add((cap, app))
    return found


def window_titles():
    """Titles of every visible top-level window."""
    titles = set()
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                titles.add(buf.value)
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return titles


def process_names():
    try:
        import psutil
    except ImportError:
        return set()
    return {
        p.info["name"]
        for p in psutil.process_iter(["name"])
        if p.info.get("name")
    }


def main():
    print("Watching. Share your screen, stop sharing, then press Ctrl+C.\n")

    caps = capabilities_in_use()
    windows = window_titles()
    procs = process_names()

    print(
        f"baseline: {len(caps)} capability holder(s), "
        f"{len(windows)} windows, {len(procs)} processes"
    )
    for cap, app in sorted(caps):
        print(f"  already held: {cap} <- {app}")
    print()

    try:
        while True:
            time.sleep(1)

            current = capabilities_in_use()
            for cap, app in sorted(current - caps):
                print(f"[capability +] {cap:34} {app}")
            for cap, app in sorted(caps - current):
                print(f"[capability -] {cap:34} {app}")
            caps = current

            current = window_titles()
            for title in sorted(current - windows):
                print(f"[window     +] {title!r}")
            for title in sorted(windows - current):
                print(f"[window     -] {title!r}")
            windows = current

            current = process_names()
            for name in sorted(current - procs):
                print(f"[process    +] {name}")
            for name in sorted(procs - current):
                print(f"[process    -] {name}")
            procs = current

    except KeyboardInterrupt:
        print("\nStopped. Paste the output above.")


if __name__ == "__main__":
    main()