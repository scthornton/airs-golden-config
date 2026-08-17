"""
Shared configuration for Golden Config experiment.

Provides auth for both APIs:
  - Management API (OAuth 2.0): profile/topic CRUD via SDK
  - Scan API (API key): real-time prompt scanning via requests
"""

import os
import sys
import json
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Credential mapping
# ---------------------------------------------------------------------------
CLIENT_ID = os.environ.get("MODEL_SECURITY_CLIENT_ID") or os.environ.get("PANW_CLIENT_ID")
CLIENT_SECRET = os.environ.get("MODEL_SECURITY_CLIENT_SECRET") or os.environ.get("PANW_CLIENT_SECRET")

# SDK releases before 0.3.0 defaulted to the auth.appsvc host, which TLS-resets
# from many networks. 0.3.0+ defaults to this endpoint; the override is kept so
# the scripts behave the same on older installs.
PROD_TOKEN_URL = "https://auth.apps.paloaltonetworks.com/am/oauth2/access_token"
PROD_BASE_URL = "https://api.sase.paloaltonetworks.com/aisec"

BASE_URL = os.environ.get("PANW_BASE_URL") or PROD_BASE_URL
TOKEN_BASE_URL = os.environ.get("PANW_TOKEN_BASE_URL") or PROD_TOKEN_URL

# Scan API
SCAN_API_URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
SCAN_API_KEY = os.environ.get("PANW_AI_SEC_API_KEY")
SECURITY_PROFILE = os.environ.get("PRISMA_AIRS_PROFILE", "redteamtest")

# State file
STATE_FILE = Path(__file__).parent / "state.json"


def validate_mgmt_credentials() -> bool:
    """Check that Management API credentials are available."""
    missing = []
    if not CLIENT_ID:
        missing.append("MODEL_SECURITY_CLIENT_ID (or PANW_CLIENT_ID)")
    if not CLIENT_SECRET:
        missing.append("MODEL_SECURITY_CLIENT_SECRET (or PANW_CLIENT_SECRET)")

    if missing:
        print(f"\n[ERROR] Missing Management API credentials:")
        for var in missing:
            print(f"  - {var}")
        return False

    print(f"[OK] Management API credentials found")
    print(f"  Client ID: {CLIENT_ID[:8]}...{CLIENT_ID[-4:]}")
    print(f"  Base URL:  {BASE_URL}")
    print(f"  Token URL: {TOKEN_BASE_URL}")
    return True


def validate_scan_credentials() -> bool:
    """Check that Scan API credentials are available."""
    if not SCAN_API_KEY:
        print(f"\n[ERROR] Missing PANW_AI_SEC_API_KEY")
        return False

    print(f"[OK] Scan API key found: {SCAN_API_KEY[:8]}...")
    print(f"  Profile: {SECURITY_PROFILE}")
    return True


def get_mgmt_client():
    """Create and return a configured MgmtClient instance."""
    from airs_api_mgmt import MgmtClient

    if not validate_mgmt_credentials():
        sys.exit(1)

    return MgmtClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        base_url=BASE_URL,
        token_base_url=TOKEN_BASE_URL,
    )


# ---------------------------------------------------------------------------
# Management SDK compatibility
# ---------------------------------------------------------------------------
# When the SDK went GA on public PyPI it renamed the "list" method on every
# resource group, and dropped the `active` field from the topic and profile
# models. Arguments and return types are otherwise unchanged.
#
#   TestPyPI alphas (<= 0.0.1a15)          PyPI GA (>= 0.0.3)
#   -----------------------------          ------------------
#   retrieve_all_custom_topics_by_tsgid    get_all_custom_topics
#   retrieve_ai_profiles                   get_all_ai_profiles
#   retrieve_all_dlp_profiles              get_all_dlp_profiles
#
# Resolving the name at call time keeps these scripts working against either
# generation, so nobody has to care which one happens to be installed.

def _resolve(resource, *candidate_names):
    """Return the first method that exists on `resource`, newest name first."""
    for name in candidate_names:
        method = getattr(resource, name, None)
        if method is not None:
            return method
    raise AttributeError(
        f"None of {candidate_names} found on {type(resource).__name__}. "
        "Check the installed pan-airs-api-mgmt-sdk version."
    )


def list_custom_topics(client, offset: int = 0, limit: int = 100):
    """List custom topics in the tenant (one page)."""
    return _resolve(
        client.custom_topics,
        "get_all_custom_topics",
        "retrieve_all_custom_topics_by_tsgid",
    )(offset=offset, limit=limit)


def list_ai_profiles(client, offset: int = 0, limit: int = 100):
    """List AI security profiles in the tenant (one page)."""
    return _resolve(
        client.ai_sec_profiles,
        "get_all_ai_profiles",
        "retrieve_ai_profiles",
    )(offset=offset, limit=limit)


def list_dlp_profiles(client):
    """List predefined DLP profiles. Note: this call takes no pagination args."""
    return _resolve(
        client.dlp_profiles,
        "get_all_dlp_profiles",
        "retrieve_all_dlp_profiles",
    )()


def optional_field(obj, name: str, default: str = "n/a"):
    """Read a model field that may not exist on this SDK version.

    `active` was removed from both CustomTopicObject and AIProfileObject in
    SDK 0.2.0, so reading it directly raises AttributeError on GA releases.
    """
    value = getattr(obj, name, None)
    return default if value is None else value


def scan_prompt(prompt: str, profile_name: str = None) -> dict:
    """Send a prompt to the AIRS Scan API. Returns the full response dict."""
    import uuid

    profile = profile_name or SECURITY_PROFILE
    payload = {
        "tr_id": str(uuid.uuid4()),
        "ai_profile": {"profile_name": profile},
        "metadata": {
            "app_user": "golden-config-tester",
            "ai_model": "claude-sonnet-4-6",
        },
        "contents": [{"prompt": prompt}],
    }

    resp = requests.post(
        SCAN_API_URL,
        headers={
            "X-Pan-Token": SCAN_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def load_state() -> dict:
    """Load state from state.json."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "profile_id": None,
        "profile_name": "golden-config-v1",
        "revision": 0,
        "topic_ids": {},
        "deployed_topics": [],
        "iteration": 0,
    }


def save_state(state: dict):
    """Persist state to state.json."""
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    print(f"  [state] Saved to {STATE_FILE}")
