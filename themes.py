"""Preview the BUSY Bar's built-in themes.

    python themes.py              # cycle through all of them
    python themes.py on_call dnd  # only the ones you name
"""

import sys
import time

from busy_bar_display import BusyBarDisplay

# The themes shipped on the device, in /ext/apps_assets/busy/themes.
THEMES = [
    "on_call",
    "meeting",
    "on_air",
    "dnd",
    "flow",
    "coding",
    "booked",
    "keep_out",
    "lunch",
    "back_soon",
    "chill_time",
    "low_social_battery",
]

HOLD_SECONDS = 4


def main():
    wanted = sys.argv[1:] or THEMES

    unknown = [t for t in wanted if t not in THEMES]
    if unknown:
        print(f"Unknown theme(s): {', '.join(unknown)}")
        print(f"Available:        {', '.join(THEMES)}")
        sys.exit(1)

    display = BusyBarDisplay()
    try:
        display.connect()
    except ConnectionError as e:
        print(f"\n{e}")
        sys.exit(1)

    print(f"\nShowing {len(wanted)} theme(s), {HOLD_SECONDS}s each. Ctrl+C to stop.\n")

    try:
        for theme in wanted:
            display.set_theme(theme)
            time.sleep(HOLD_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        display.clear_display()


if __name__ == "__main__":
    main()