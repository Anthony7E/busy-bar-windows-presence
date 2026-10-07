import argparse
import sys
import time

from busy_bar_display import BusyBarDisplay
from config import (
    BUSY_BAR_LAN_IP,
    DEFAULT_THEME,
    POLL_INTERVAL,
    PRESENCE_SOURCE,
    THEME_MAP,
)
from log import log


def build_source(name):
    """Return a zero-argument callable that yields a presence dict."""
    if name == "local":
        import local_presence

        log("Presence source: local sensors (no authentication required)")
        return local_presence.get_presence

    if name == "graph":
        import teams_presence

        log("Presence source: Microsoft Graph")
        token = {"value": teams_presence.authenticate()}

        def fetch():
            presence = teams_presence.get_presence(token["value"])
            if presence is None:
                token["value"] = teams_presence.refresh_token_if_needed(token["value"])
                presence = teams_presence.get_presence(token["value"])
            return presence

        return fetch

    raise ValueError(f"Unknown presence source: {name}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mirror your Teams presence onto a BUSY Bar."
    )
    parser.add_argument(
        "--source",
        choices=["local", "graph"],
        default=PRESENCE_SOURCE,
        help="Where to read presence from (default: %(default)s)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=POLL_INTERVAL,
        help="Seconds between polls (default: %(default)s)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print one reading and exit without touching the BUSY Bar",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the underlying signals on every poll",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Left unstamped on purpose: in an appended log file this banner is what
    # visibly marks the start of a new run.
    print("Teams Presence -> BUSY Bar")
    print("-" * 34)

    get_presence = build_source(args.source)

    if args.once:
        presence = get_presence()
        theme = THEME_MAP.get(presence["availability"], DEFAULT_THEME)
        print(f"availability: {presence['availability']}")
        print(f"would show:   {theme or 'idle (no session)'}")
        if presence.get("signals"):
            print(f"signals:      {presence['signals']}")
        return

    display = BusyBarDisplay()
    try:
        display.connect()
    except ConnectionError as e:
        log(str(e))
        print("Set BUSY_BAR_LAN_TOKEN (device PIN) or BUSY_BAR_API_TOKEN (cloud) in .env.")
        print(f"Also confirm {BUSY_BAR_LAN_IP} is reachable: Test-NetConnection {BUSY_BAR_LAN_IP} -Port 80")
        sys.exit(1)

    last_availability = None

    log(f"Polling every {args.interval}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                presence = get_presence()
                if presence is None:
                    log("Could not read presence; retrying.")
                    time.sleep(args.interval)
                    continue

                availability = presence["availability"]

                if availability != last_availability:
                    if last_availability is None:
                        log(availability)
                    else:
                        log(f"{last_availability} -> {availability}")
                    last_availability = availability

                # set_theme is a no-op when the theme has not changed, so the
                # running animation is never restarted mid-poll.
                display.set_theme(THEME_MAP.get(availability, DEFAULT_THEME))

                if args.verbose and presence.get("signals"):
                    log(f"  signals: {presence['signals']}")

            except Exception as e:
                log(f"Error: {e}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("Shutting down...")
    finally:
        display.clear_display()


if __name__ == "__main__":
    main()