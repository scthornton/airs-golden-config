#!/usr/bin/env python3
"""
DLP Data Profile operations for Golden Config experiment.

Lists available DLP profiles from the tenant and attaches them
to the AIRS security profile via the Management API.

Usage:
    python dlp_ops.py list                          # List all available DLP profiles
    python dlp_ops.py attach --names "PII" "Profanity"  # Attach specific profiles
    python dlp_ops.py attach --tier1                # Attach all Tier 1 profiles
    python dlp_ops.py show                          # Show DLP config on security profile
    python dlp_ops.py detach                        # Remove all DLP profiles from security profile
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from config import get_mgmt_client, load_state, save_state

# Tier 1 DLP profiles — universal, safe to enable for any deployment
TIER1_PROFILES = [
    "Secrets and Credentials",
    "PII",
    "Sensitive Content",
    "Profanity",
    "Self Harm",
]


def get_available_dlp_profiles(client) -> list[dict]:
    """List all DLP profiles available on the tenant."""
    response = client.dlp_profiles.retrieve_all_dlp_profiles()
    profiles = []
    for p in (response.dlp_profiles or []):
        # Convert SDK object to dict
        if hasattr(p, "model_dump"):
            profiles.append(p.model_dump())
        elif hasattr(p, "__dict__"):
            profiles.append({k: v for k, v in p.__dict__.items() if not k.startswith("_")})
        else:
            profiles.append(p)
    return profiles


def get_current_profile(client, profile_id: str) -> dict:
    """Retrieve the current security profile as a dict."""
    response = client.ai_sec_profiles.retrieve_ai_profiles(offset=0, limit=100)
    for profile in (response.ai_profiles or []):
        if profile.profile_id == profile_id:
            if hasattr(profile, "model_dump"):
                return profile.model_dump()
            return profile
    return None


def cmd_list(args):
    """List all available DLP profiles on the tenant."""
    client = get_mgmt_client()
    profiles = get_available_dlp_profiles(client)

    print(f"\n  {len(profiles)} DLP profile(s) available:\n")
    print(f"  {'#':>3}  {'Name':<35}  {'UUID':<38}  Tier1?")
    print(f"  {'─'*3}  {'─'*35}  {'─'*38}  {'─'*5}")

    for i, p in enumerate(profiles, 1):
        name = p.get("name", "?")
        uuid = p.get("uuid", "?")
        is_tier1 = "  ✓" if name in TIER1_PROFILES else ""
        print(f"  {i:>3}  {name:<35}  {uuid:<38}{is_tier1}")

    tier1_found = [p for p in profiles if p.get("name") in TIER1_PROFILES]
    print(f"\n  Tier 1 profiles found: {len(tier1_found)}/{len(TIER1_PROFILES)}")


def cmd_show(args):
    """Show current DLP configuration on the security profile."""
    client = get_mgmt_client()
    state = load_state()

    profile_id = state.get("profile_id")
    if not profile_id:
        print("[ERROR] No profile_id in state.json. Run 'profile_ops.py create' first.")
        return

    profile = get_current_profile(client, profile_id)
    if not profile:
        print(f"[ERROR] Profile {profile_id} not found in tenant.")
        return

    policy = profile.get("policy", {})
    dlp_profiles = policy.get("dlp-data-profiles") or policy.get("dlp_data_profiles") or []

    print(f"\n  Profile: {profile.get('profile_name')} (rev {profile.get('revision')})")
    print(f"  DLP profiles attached: {len(dlp_profiles)}\n")

    if dlp_profiles:
        for i, dp in enumerate(dlp_profiles, 1):
            name = dp.get("name", "?")
            uuid = dp.get("uuid", "?")
            r1 = dp.get("rule1", {}).get("action", "?")
            r2 = dp.get("rule2", {}).get("action", "?")
            print(f"  {i}. {name}  (rule1={r1}, rule2={r2})")
    else:
        print("  (none)")

    print(f"\n  Full DLP policy section:")
    print(f"  {json.dumps(dlp_profiles, indent=4)}")


def cmd_attach(args):
    """Attach DLP profiles to the security profile."""
    client = get_mgmt_client()
    state = load_state()

    profile_id = state.get("profile_id")
    if not profile_id:
        print("[ERROR] No profile_id in state.json.")
        return

    # Get available DLP profiles
    available = get_available_dlp_profiles(client)
    available_by_name = {p.get("name"): p for p in available}

    # Determine which to attach
    if args.tier1:
        target_names = TIER1_PROFILES
    elif args.names:
        target_names = args.names
    else:
        print("[ERROR] Specify --tier1 or --names 'Profile1' 'Profile2'")
        return

    # Resolve names to full profile objects
    to_attach = []
    for name in target_names:
        if name in available_by_name:
            to_attach.append(available_by_name[name])
            print(f"  [OK] Found: {name} ({available_by_name[name].get('uuid', '?')})")
        else:
            # Try partial match
            matches = [n for n in available_by_name if name.lower() in n.lower()]
            if matches:
                matched = matches[0]
                to_attach.append(available_by_name[matched])
                print(f"  [OK] Matched '{name}' → {matched}")
            else:
                print(f"  [WARN] Not found: {name}")

    if not to_attach:
        print("\n[ERROR] No DLP profiles resolved. Run 'list' to see available.")
        return

    # Build DLP profile entries for the policy
    # The API expects hyphenated keys (log-severity, non-file-based, file-based)
    # but the SDK returns underscored keys (log_severity, non_file_based, file_based)
    dlp_entries = []
    for p in to_attach:
        entry = {
            "name": p.get("name"),
            "uuid": p.get("uuid", ""),
            "id": p.get("id", ""),
            "version": p.get("version", ""),
        }
        # Rule actions — override to block for our golden config
        # Pre-built profiles default to "alert" but we want "block"
        entry["rule1"] = {"action": "block"}
        entry["rule2"] = {"action": "block"}

        # Map SDK underscore fields to API hyphenated fields
        entry["log-severity"] = (
            p.get("log-severity")
            or p.get("log_severity")
            or "high"
        )
        entry["non-file-based"] = (
            p.get("non-file-based")
            or p.get("non_file_based")
            or ""
        )
        entry["file-based"] = (
            p.get("file-based")
            or p.get("file_based")
            or ""
        )
        dlp_entries.append(entry)

    # Get current profile
    profile = get_current_profile(client, profile_id)
    if not profile:
        print(f"[ERROR] Profile {profile_id} not found.")
        return

    # Update policy with DLP profiles
    policy = profile.get("policy", {})
    policy["dlp-data-profiles"] = dlp_entries

    new_revision = profile.get("revision", 1) + 1
    profile_name = profile.get("profile_name", state.get("profile_name"))

    print(f"\n  Attaching {len(dlp_entries)} DLP profile(s) to {profile_name} (rev {new_revision})...")

    try:
        response = client.ai_sec_profiles.update_ai_profile(
            profile_id=profile_id,
            profile_name=profile_name,
            revision=new_revision,
            policy=policy,
            active=True,
            updated_by="golden-config@perfecxion.ai",
        )

        # Update state
        state["profile_id"] = response.profile_id
        state["revision"] = response.revision
        save_state(state)

        print(f"\n  [OK] Profile updated → revision {response.revision}")
        print(f"  New profile ID: {response.profile_id}")
        print(f"  DLP profiles attached: {len(dlp_entries)}")
        for e in dlp_entries:
            print(f"    - {e['name']}")

    except Exception as e:
        print(f"\n  [FAIL] Profile update failed: {e}")
        print(f"\n  Trying with single-profile fallback...")

        # If multi-profile fails, try attaching just one at a time
        # or report the exact error for debugging
        err_str = str(e)
        if "dlp" in err_str.lower() or "array" in err_str.lower():
            print(f"\n  The API may not accept multiple DLP profiles in the array.")
            print(f"  Try attaching one at a time: python dlp_ops.py attach --names '{to_attach[0].get('name')}'")
        else:
            print(f"\n  Full error: {err_str}")


def cmd_detach(args):
    """Remove all DLP profiles from the security profile."""
    client = get_mgmt_client()
    state = load_state()

    profile_id = state.get("profile_id")
    if not profile_id:
        print("[ERROR] No profile_id in state.json.")
        return

    profile = get_current_profile(client, profile_id)
    if not profile:
        print(f"[ERROR] Profile {profile_id} not found.")
        return

    policy = profile.get("policy", {})
    policy["dlp-data-profiles"] = []

    new_revision = profile.get("revision", 1) + 1
    profile_name = profile.get("profile_name", state.get("profile_name"))

    print(f"\n  Detaching all DLP profiles from {profile_name} (rev {new_revision})...")

    response = client.ai_sec_profiles.update_ai_profile(
        profile_id=profile_id,
        profile_name=profile_name,
        revision=new_revision,
        policy=policy,
        active=True,
        updated_by="golden-config@perfecxion.ai",
    )

    state["profile_id"] = response.profile_id
    state["revision"] = response.revision
    save_state(state)

    print(f"  [OK] DLP profiles cleared. Profile revision: {response.revision}")


def main():
    parser = argparse.ArgumentParser(description="Golden Config — DLP Profile Ops")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List available DLP profiles on tenant")
    sub.add_parser("show", help="Show DLP config on current security profile")
    sub.add_parser("detach", help="Remove all DLP profiles from security profile")

    attach_p = sub.add_parser("attach", help="Attach DLP profiles to security profile")
    attach_p.add_argument("--tier1", action="store_true", help="Attach all Tier 1 profiles")
    attach_p.add_argument("--names", nargs="+", help="Attach specific profiles by name")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        "list": cmd_list,
        "show": cmd_show,
        "attach": cmd_attach,
        "detach": cmd_detach,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
