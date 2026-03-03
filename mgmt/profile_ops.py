#!/usr/bin/env python3
"""
Security Profile CRUD for Golden Config experiment.

Usage:
    python profile_ops.py create              # Create baseline blocking profile
    python profile_ops.py show                # Show current profile details
    python profile_ops.py update              # Update to latest policy
    python profile_ops.py delete              # Delete profile
    python profile_ops.py list                # List all profiles in tenant
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from config import get_mgmt_client, load_state, save_state


def build_policy(
    timeout_action="block",
    max_latency=20,
    prompt_injection_action="block",
    jailbreak_action="block",
    data_leak_action="block",
    url_action="block",
):
    """Build a maximally-blocking AI security profile policy.

    This is the 'golden config' — everything blocked, short timeout.
    The goal is 0% ASR against red team scans.
    """
    return {
        "dlp-data-profiles": [],
        "ai-security-profiles": [
            {
                "model-type": "default",
                "model-configuration": {
                    "latency": {
                        "inline-timeout-action": timeout_action,
                        "max-inline-latency": max_latency,
                    },
                    "data-protection": {
                        "data-leak-detection": {
                            "member": [
                                {"text": "Sensitive Content", "id": "", "version": "2"}
                            ],
                            "action": data_leak_action,
                        }
                    },
                    "app-protection": {
                        "default-url-category": {"member": ["malicious"]},
                        "url-detected-action": url_action,
                    },
                    "model-protection": [
                        {"name": "prompt-injection", "action": prompt_injection_action},
                        {"name": "jailbreak", "action": jailbreak_action},
                    ],
                },
            }
        ],
    }


def cmd_create(args):
    """Create the golden-config security profile."""
    client = get_mgmt_client()
    state = load_state()

    if state.get("profile_id"):
        print(f"[WARN] Profile already exists: {state['profile_id']}")
        print(f"  Run 'delete' first, or 'show' to inspect.")
        return

    profile_name = state.get("profile_name", "golden-config-v1")
    policy = build_policy()

    print(f"\nCreating profile: {profile_name}")
    print(f"  Policy: all detections → BLOCK, timeout → BLOCK/20s")

    response = client.ai_sec_profiles.create_new_ai_profile(
        profile_name=profile_name,
        revision=1,
        policy=policy,
        active=True,
        created_by="golden-config@perfecxion.ai",
    )

    state["profile_id"] = response.profile_id
    state["revision"] = response.revision
    save_state(state)

    print(f"\n  [OK] Profile created")
    print(f"  ID:       {response.profile_id}")
    print(f"  Name:     {response.profile_name}")
    print(f"  Revision: {response.revision}")
    print(f"  Active:   {response.active}")


def cmd_show(args):
    """Show current profile details."""
    client = get_mgmt_client()
    state = load_state()

    profile_id = state.get("profile_id")
    if not profile_id:
        print("[INFO] No profile in state.json. Listing all profiles...")
        cmd_list(args)
        return

    response = client.ai_sec_profiles.retrieve_ai_profiles(offset=0, limit=100)

    found = None
    for profile in (response.ai_profiles or []):
        if profile.profile_id == profile_id:
            found = profile
            break

    if found:
        print(f"\n  Profile: {found.profile_name}")
        print(f"  ID:      {found.profile_id}")
        print(f"  Active:  {found.active}")
        print(f"  Rev:     {found.revision}")
        if hasattr(found, "policy") and found.policy:
            import json
            print(f"\n  Policy:\n{json.dumps(found.policy, indent=4)}")
    else:
        print(f"[WARN] Profile {profile_id} not found in tenant")
        print(f"  State may be stale. Run 'list' to see available profiles.")


def cmd_update(args):
    """Update the profile with the latest golden-config policy."""
    client = get_mgmt_client()
    state = load_state()

    profile_id = state.get("profile_id")
    if not profile_id:
        print("[ERROR] No profile_id in state. Run 'create' first.")
        return

    new_revision = state.get("revision", 1) + 1
    policy = build_policy()

    print(f"\nUpdating profile {profile_id} → revision {new_revision}")

    response = client.ai_sec_profiles.update_ai_profile(
        profile_id=profile_id,
        profile_name=state.get("profile_name", "golden-config-v1"),
        revision=new_revision,
        policy=policy,
        active=True,
        updated_by="golden-config@perfecxion.ai",
    )

    state["revision"] = response.revision
    save_state(state)

    print(f"  [OK] Profile updated to revision {response.revision}")


def cmd_delete(args):
    """Delete the golden-config profile."""
    client = get_mgmt_client()
    state = load_state()

    profile_id = state.get("profile_id")
    if not profile_id:
        print("[INFO] No profile in state.json — nothing to delete.")
        return

    print(f"\nDeleting profile: {profile_id}")

    try:
        client.ai_sec_profiles.delete_ai_profile(profile_id=profile_id)
        print(f"  [OK] Profile deleted")
    except Exception as e:
        print(f"  Standard delete failed: {e}")
        print(f"  Attempting force delete...")
        client.ai_sec_profiles.force_delete_ai_profile(
            profile_id=profile_id,
            updated_by="golden-config@perfecxion.ai",
        )
        print(f"  [OK] Profile force-deleted")

    state["profile_id"] = None
    state["revision"] = 0
    save_state(state)


def cmd_list(args):
    """List all profiles in the tenant."""
    client = get_mgmt_client()

    response = client.ai_sec_profiles.retrieve_ai_profiles(offset=0, limit=100)

    profiles = response.ai_profiles or []
    print(f"\n  Found {len(profiles)} profile(s):\n")
    for p in profiles:
        print(f"  [{p.profile_id}] {p.profile_name}  active={p.active}  rev={p.revision}")


def main():
    parser = argparse.ArgumentParser(description="Golden Config — Security Profile Ops")
    parser.add_argument("command", choices=["create", "show", "update", "delete", "list"])
    args = parser.parse_args()

    cmds = {
        "create": cmd_create,
        "show": cmd_show,
        "update": cmd_update,
        "delete": cmd_delete,
        "list": cmd_list,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
