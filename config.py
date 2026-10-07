import os
from dotenv import load_dotenv

load_dotenv()

# Presence source: "local" (registry sensors) or "graph" (Microsoft Graph API)
PRESENCE_SOURCE = os.getenv("PRESENCE_SOURCE", "local").lower()

# --- Microsoft Graph (blocked by Conditional Access on this tenant; kept for future use) ---
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_SCOPES = ["Presence.Read"]

# --- BUSY Bar connection ---
BUSY_BAR_LAN_IP = os.getenv("BUSY_BAR_LAN_IP", "192.168.1.100")
BUSY_BAR_LAN_TOKEN = os.getenv("BUSY_BAR_LAN_TOKEN", "")
BUSY_BAR_API_TOKEN = os.getenv("BUSY_BAR_API_TOKEN", "")

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

APP_NAME = "teams-presence"

# Starting a BUSY session can also switch paired smart-home lights. Off by
# default so mirroring presence does not quietly take over your room.
TRIGGER_SMART_HOME = os.getenv("TRIGGER_SMART_HOME", "false").lower() == "true"

# --- Local detection tuning ---
# Seconds of no keyboard/mouse input before reporting AWAY.
IDLE_THRESHOLD = int(os.getenv("IDLE_THRESHOLD", "300"))

# Packaged (MSIX/Store) apps, keyed by Package Family Name.
MONITORED_PACKAGED_APPS = [
    "MSTeams_8wekyb3d8bbwe",
]

# Classic win32 apps, matched on the executable name.
MONITORED_EXE_APPS = [
    "Teams.exe",
    "Zoom.exe",
]

# Browsers are opt-in: an open mic in a browser tab is often not a meeting.
INCLUDE_BROWSERS = os.getenv("INCLUDE_BROWSERS", "false").lower() == "true"
BROWSER_EXE_APPS = [
    "chrome.exe",
    "msedge.exe",
]

# Process names that indicate Teams is running at all.
TEAMS_PROCESS_NAMES = [
    "ms-teams.exe",
    "Teams.exe",
]

# Teams never registers screen capture with the Capability Access Manager, so
# the registry cannot see a share. It does open a floating indicator window for
# exactly the duration of the share, which is a dependable stand-in.
#
# These are substrings, matched case-insensitively against visible window
# titles. Window titles are localised, so override this for a non-English UI
# or to cover another conferencing app. Run diagnose_share.py while sharing to
# find the right string - look for the title that disappears when you stop.
SCREEN_SHARE_WINDOW_TITLES = [
    title.strip()
    for title in os.getenv(
        "SCREEN_SHARE_WINDOW_TITLES", "Sharing control bar"
    ).split(",")
    if title.strip()
]

# --- Display mapping ---
# Each value is one of the device's built-in BUSY themes, rendered natively by
# the bar (icon + label + animation). Run `python themes.py` to preview them.
#
# Available themes: back_soon, booked, chill_time, coding, dnd, flow, keep_out,
#                   low_social_battery, lunch, meeting, on_air, on_call
#
# None means "stop the BUSY session", which returns the bar to its idle screen.
THEME_MAP = {
    "Available":        None,
    "Offline":          None,
    "PresenceUnknown":  None,
    "InACall":          "on_call",      # microphone only
    "InAVideoCall":     "meeting",      # microphone + camera
    "InAMeeting":       "meeting",
    "Presenting":       "on_air",       # sharing your screen
    "Busy":             "dnd",
    "DoNotDisturb":     "dnd",
    "Focusing":         "flow",
    "Away":             "back_soon",
    "BeRightBack":      "back_soon",
}

DEFAULT_THEME = None