import json
import os
import sys

import msal
import requests

from config import AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SCOPES

GRAPH_PRESENCE_URL = "https://graph.microsoft.com/v1.0/me/presence"
CACHE_FILE = os.path.join(os.path.dirname(__file__), ".token_cache.json")
AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}" if AZURE_TENANT_ID else "https://login.microsoftonline.com/common"


def _build_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache.deserialize(f.read())
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        with open(CACHE_FILE, "w") as f:
            f.write(cache.serialize())


def _get_app(cache):
    return msal.PublicClientApplication(
        AZURE_CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )


def authenticate():
    if not AZURE_CLIENT_ID:
        print("Error: AZURE_CLIENT_ID not set in .env file.")
        sys.exit(1)

    cache = _build_cache()
    app = _get_app(cache)

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(AZURE_SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(cache)
            return result["access_token"]

    print("Opening browser for Microsoft login...")
    print("(If browser doesn't open, check the console for a URL to visit.)")
    result = app.acquire_token_interactive(AZURE_SCOPES)

    if "access_token" in result:
        _save_cache(cache)
        print("Authentication successful.")
        return result["access_token"]

    print(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
    sys.exit(1)


def get_presence(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    response = requests.get(GRAPH_PRESENCE_URL, headers=headers, timeout=10)

    if response.status_code == 401:
        return None

    response.raise_for_status()
    data = response.json()
    return {
        "availability": data.get("availability", "PresenceUnknown"),
        "activity": data.get("activity", "PresenceUnknown"),
        "status_message": data.get("statusMessage"),
    }


def refresh_token_if_needed(current_token):
    cache = _build_cache()
    app = _get_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        return authenticate()

    result = app.acquire_token_silent(AZURE_SCOPES, account=accounts[0])
    if result and "access_token" in result:
        _save_cache(cache)
        return result["access_token"]

    return authenticate()