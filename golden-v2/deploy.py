#!/usr/bin/env python3
"""
Deploy golden-v2 topics and profile to AIRS calibration tenant.

Usage:
    python deploy.py                          # Full deploy (topics + profile)
    python deploy.py --topics-only            # Only deploy/update topics
    python deploy.py --profile-name golden-v2 # Custom profile name
"""
import argparse
import json
import os
import sys
from pathlib import Path

from airs_api_mgmt import MgmtClient

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state.json"
TOPICS_FILE = ROOT / "topics.json"

DLP_TIER1 = {
    "PII": "11995018",
    "Secrets and Credentials": "11995023",
    "Sensitive Content": "11995025",
    "Self Harm": "11995024",
    "Profanity": "11995021",
}


def get_client():
    cid = os.environ.get("MODEL_SECURITY_CLIENT_ID") or os.environ.get("PANW_CLIENT_ID")
    csec = os.environ.get("MODEL_SECURITY_CLIENT_SECRET") or os.environ.get("PANW_CLIENT_SECRET")
    if not (cid and csec):
        print("[ERROR] Set MODEL_SECURITY_CLIENT_ID + MODEL_SECURITY_CLIENT_SECRET")
        sys.exit(1)
    return MgmtClient(
        client_id=cid, client_secret=csec,
        base_url="https://api.sase.paloaltonetworks.com/aisec",
        token_base_url="https://auth.apps.paloaltonetworks.com/oauth2/access_token",
    )


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"topic_ids": {}, "topic_revisions": {}, "profile_id": None, "revision": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"  [state] Saved to {STATE_FILE}")


def deploy_topics(client):
    topics_data = json.loads(TOPICS_FILE.read_text())
    topics = topics_data["topics"]
    state = load_state()

    existing = client.custom_topics.retrieve_all_custom_topics_by_tsgid(offset=0, limit=200)
    existing_by_name = {t.topic_name: t for t in (existing.custom_topics or [])}

    deployed = dict(state.get("topic_ids", {}))
    revisions = dict(state.get("topic_revisions", {}))

    print(f"\n--- Deploying {len(topics)} topics ---")

    for t in topics:
        name = t["topic_name"]
        desc = t["description"]
        examples = t.get("examples", [])

        if name in existing_by_name:
            tid = existing_by_name[name].topic_id
            current_rev = revisions.get(name, 1)
            new_rev = current_rev + 1
            try:
                client.custom_topics.modify_custom_topic_details(
                    topic_id=tid,
                    topic_name=name,
                    description=desc,
                    examples=examples,
                    revision=new_rev,
                    updated_by="golden-v2@perfecxion.ai",
                )
                deployed[name] = tid
                revisions[name] = new_rev
                print(f"  [updated] {name} rev {current_rev}->{new_rev} ({tid[:12]}...)")
            except Exception as e:
                deployed[name] = tid
                revisions[name] = current_rev
                print(f"  [exists]  {name} ({tid[:12]}...) update failed: {e}")
        else:
            try:
                resp = client.custom_topics.create_new_custom_topic(
                    topic_name=name,
                    description=desc,
                    examples=examples,
                    revision=1,
                    created_by="golden-v2@perfecxion.ai",
                    active=True,
                )
                deployed[name] = resp.topic_id
                revisions[name] = 1
                print(f"  [created] {name} ({resp.topic_id[:12]}...)")
            except Exception as e:
                err = str(e)
                if "409" in err or "conflict" in err.lower():
                    refetch = client.custom_topics.retrieve_all_custom_topics_by_tsgid(offset=0, limit=200)
                    for tp in (refetch.custom_topics or []):
                        if tp.topic_name == name:
                            deployed[name] = tp.topic_id
                            revisions[name] = 1
                            print(f"  [409->got] {name} ({tp.topic_id[:12]}...)")
                            break
                else:
                    print(f"  [FAIL]    {name}: {e}")

    state["topic_ids"] = deployed
    state["topic_revisions"] = revisions
    save_state(state)
    print(f"\n  {len(deployed)} topics ready")
    return state


def build_policy(topic_ids):
    blocked_topics = [
        {"topic_name": name, "topic_id": tid, "revision": 1}
        for name, tid in topic_ids.items()
    ]

    topic_list = [
        {"action": "allow", "topic": []},
        {"action": "block", "topic": blocked_topics},
    ]

    return {
        "dlp-data-profiles": [
            {
                "name": name, "uuid": "", "id": dlp_id, "version": "1",
                "rule1": {"action": "alert"}, "rule2": {"action": ""},
                "log-severity": "medium", "non-file-based": "", "file-based": "",
            }
            for name, dlp_id in DLP_TIER1.items()
        ],
        "ai-security-profiles": [{
            "model-type": "default",
            "model-configuration": {
                "mask-data-in-storage": False,
                "latency": {"inline-timeout-action": "block", "max-inline-latency": 25},
                "data-protection": {
                    "data-leak-detection": {
                        "member": [
                            {"text": name, "id": dlp_id, "version": "1"}
                            for name, dlp_id in DLP_TIER1.items()
                        ],
                        "action": "block",
                    }
                },
                "app-protection": {
                    "block-url-category": {},
                    "allow-url-category": {},
                    "default-url-category": {"member": ["malicious"]},
                    "url-detected-action": "block",
                    "malicious-code-protection": {"name": "malicious-code", "action": "block"},
                },
                "model-protection": [
                    {"name": "prompt-injection", "action": "block"},
                    {"name": "contextual-grounding", "action": "block"},
                    {"name": "toxic-content", "action": "high:block, moderate:block"},
                    {
                        "name": "topic-guardrails",
                        "action": "allow",
                        "topic-list": topic_list,
                    },
                ],
                "agent-protection": [
                    {"name": "agent-security", "action": "block"}
                ],
            },
        }],
    }


def deploy_profile(client, state, profile_name):
    policy = build_policy(state["topic_ids"])

    existing = client.ai_sec_profiles.retrieve_ai_profiles(offset=0, limit=200)
    matches = [p for p in (existing.ai_profiles or []) if p.profile_name == profile_name]

    if matches:
        latest = max(matches, key=lambda p: p.revision)
        new_rev = latest.revision + 1
        print(f"  [update] {profile_name}: rev {latest.revision} -> {new_rev}")
        resp = client.ai_sec_profiles.update_ai_profile(
            profile_id=latest.profile_id,
            profile_name=profile_name,
            revision=new_rev,
            policy=policy,
            updated_by="golden-v2@perfecxion.ai",
        )
        state["profile_id"] = resp.profile_id
        state["revision"] = resp.revision
    else:
        print(f"  [create] {profile_name}: new profile")
        resp = client.ai_sec_profiles.create_new_ai_profile(
            profile_name=profile_name,
            revision=1,
            policy=policy,
            created_by="golden-v2@perfecxion.ai",
        )
        state["profile_id"] = resp.profile_id
        state["revision"] = resp.revision

    save_state(state)
    print(f"  [OK] {profile_name} = {resp.profile_id} (rev {resp.revision})")
    print(f"\n  Wait ~5 min for cache propagation before testing.")
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-name", default="golden-v2")
    parser.add_argument("--topics-only", action="store_true")
    args = parser.parse_args()

    client = get_client()
    state = deploy_topics(client)

    if not args.topics_only:
        print(f"\n--- Deploying profile: {args.profile_name} ---")
        print(f"  Topics: {len(state['topic_ids'])}")
        print(f"  Built-ins: PI(block), toxic(block/block), malcode(block), url(block), agent(block)")
        print(f"  DLP: {len(DLP_TIER1)} Tier 1 profiles")
        deploy_profile(client, state, args.profile_name)


if __name__ == "__main__":
    main()
