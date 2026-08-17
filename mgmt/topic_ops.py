#!/usr/bin/env python3
"""
Custom Topic management for Golden Config experiment.

Reads topic definitions from the prisma-airs-custom-topics library
and deploys them via the Management API.

Usage:
    python topic_ops.py list                  # List deployed topics in tenant
    python topic_ops.py library               # Show available topics from library
    python topic_ops.py deploy --top 20       # Deploy top 20 topics by attack count
    python topic_ops.py deploy --names t1 t2  # Deploy specific topics by name
    python topic_ops.py remove --all          # Remove all deployed topics
    python topic_ops.py remove --name foo     # Remove a specific topic
    python topic_ops.py sync                  # Sync state.json with tenant
"""

import sys
import os
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from config import get_mgmt_client, load_state, save_state, list_custom_topics

# Topic library location
TOPIC_LIB = Path(__file__).parent.parent.parent / "prisma-airs-custom-topics" / "topics"
MAX_TOPICS_PER_PROFILE = 20


def load_library() -> list[dict]:
    """Load all topics from the topic library, sorted by successful_attacks desc."""
    if not TOPIC_LIB.exists():
        print(f"[ERROR] Topic library not found: {TOPIC_LIB}")
        sys.exit(1)

    all_topics = []
    for f in sorted(TOPIC_LIB.glob("*.json")):
        data = json.loads(f.read_text())
        category = data.get("category", f.stem)
        for topic in data.get("topics", []):
            topic["_category"] = category
            topic["_file"] = f.name
            all_topics.append(topic)

    # Sort by successful_attacks (highest first) for priority deployment
    all_topics.sort(
        key=lambda t: t.get("red_team_data", {}).get("successful_attacks", 0),
        reverse=True,
    )
    return all_topics


def cmd_library(args):
    """Show available topics from the library."""
    topics = load_library()

    print(f"\n  Topic Library: {len(topics)} topics available")
    print(f"  (Max {MAX_TOPICS_PER_PROFILE} per profile)\n")
    print(f"  {'#':>3}  {'Attacks':>7}  {'Priority':<8}  {'Category':<22}  Name")
    print(f"  {'─'*3}  {'─'*7}  {'─'*8}  {'─'*22}  {'─'*30}")

    for i, t in enumerate(topics, 1):
        attacks = t.get("red_team_data", {}).get("successful_attacks", 0)
        priority = t.get("priority", "—")
        category = t.get("_category", "—")
        name = t.get("topic_name", "—")
        marker = " ◀" if i <= MAX_TOPICS_PER_PROFILE else ""
        print(f"  {i:>3}  {attacks:>7}  {priority:<8}  {category:<22}  {name}{marker}")

    print(f"\n  ◀ = included in top-{MAX_TOPICS_PER_PROFILE} deployment")


def load_from_file(filepath: str) -> list[dict]:
    """Load topics from a custom JSON file (golden_topics.json format)."""
    path = Path(filepath)
    if not path.exists():
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)

    data = json.loads(path.read_text())
    topics = data.get("topics", [])
    print(f"  Loaded {len(topics)} topic(s) from {path.name}")
    return topics


def cmd_deploy(args):
    """Deploy topics from the library or a custom file to the tenant."""
    client = get_mgmt_client()
    state = load_state()

    # Load topics from custom file or library
    if args.file:
        library = load_from_file(args.file)
    else:
        library = load_library()

    # Determine which topics to deploy
    if args.names:
        to_deploy = [t for t in library if t["topic_name"] in args.names]
        missing = set(args.names) - {t["topic_name"] for t in to_deploy}
        if missing:
            print(f"[WARN] Topics not found in library: {missing}")
    else:
        limit = min(args.top, MAX_TOPICS_PER_PROFILE)
        to_deploy = library[:limit]

    if not to_deploy:
        print("[INFO] No topics to deploy.")
        return

    print(f"\n  Deploying {len(to_deploy)} topic(s)...\n")
    deployed = state.get("topic_ids", {})
    new_count = 0

    for topic in to_deploy:
        name = topic["topic_name"]

        if name in deployed:
            print(f"  [skip] {name} — already deployed ({deployed[name]})")
            continue

        # Extract only the fields the API expects
        try:
            response = client.custom_topics.create_new_custom_topic(
                topic_name=name,
                description=topic["description"],
                examples=topic["examples"],
                revision=1,
                created_by="golden-config@perfecxion.ai",
                active=True,
            )
            deployed[name] = response.topic_id
            new_count += 1
            print(f"  [OK]   {name} → {response.topic_id}")

        except Exception as e:
            err_str = str(e)
            if "409" in err_str or "conflict" in err_str.lower():
                print(f"  [409]  {name} — already exists in tenant, fetching ID...")
                # Try to find it in tenant listing
                existing = list_custom_topics(client, offset=0, limit=100)
                for t in (existing.custom_topics or []):
                    if t.topic_name == name:
                        deployed[name] = t.topic_id
                        print(f"         Found: {t.topic_id}")
                        break
            else:
                print(f"  [FAIL] {name} — {e}")

    state["topic_ids"] = deployed
    state["deployed_topics"] = list(deployed.keys())
    save_state(state)
    print(f"\n  Deployed {new_count} new topic(s). Total: {len(deployed)}")


def cmd_list(args):
    """List topics currently deployed in the tenant."""
    client = get_mgmt_client()

    response = list_custom_topics(client, offset=0, limit=100)

    topics = response.custom_topics or []
    print(f"\n  {len(topics)} topic(s) in tenant:\n")
    for t in topics:
        desc_preview = (t.description[:60] + "...") if len(t.description) > 60 else t.description
        ex_count = len(t.examples) if t.examples else 0
        print(f"  [{t.topic_id}] {t.topic_name}")
        print(f"     {desc_preview}  ({ex_count} examples)")


def cmd_remove(args):
    """Remove topics from the tenant."""
    client = get_mgmt_client()
    state = load_state()
    deployed = state.get("topic_ids", {})

    if args.all:
        targets = list(deployed.items())
    elif args.name:
        if args.name in deployed:
            targets = [(args.name, deployed[args.name])]
        else:
            print(f"[ERROR] Topic '{args.name}' not in state.json")
            return
    else:
        print("[ERROR] Specify --all or --name <topic_name>")
        return

    if not targets:
        print("[INFO] No topics to remove.")
        return

    print(f"\n  Removing {len(targets)} topic(s)...\n")
    for name, topic_id in targets:
        try:
            client.custom_topics.delete_custom_topic(topic_id=topic_id)
            del deployed[name]
            print(f"  [OK] Deleted {name} ({topic_id})")
        except Exception as e:
            print(f"  [FAIL] {name} — {e}")

    state["topic_ids"] = deployed
    state["deployed_topics"] = list(deployed.keys())
    save_state(state)


def cmd_sync(args):
    """Sync state.json with what's actually in the tenant."""
    client = get_mgmt_client()
    state = load_state()

    response = list_custom_topics(client, offset=0, limit=100)

    tenant_topics = {}
    for t in (response.custom_topics or []):
        tenant_topics[t.topic_name] = t.topic_id

    state["topic_ids"] = tenant_topics
    state["deployed_topics"] = list(tenant_topics.keys())
    save_state(state)

    print(f"\n  [OK] Synced state with tenant: {len(tenant_topics)} topic(s)")
    for name, tid in tenant_topics.items():
        print(f"    {name} → {tid}")


def main():
    parser = argparse.ArgumentParser(description="Golden Config — Topic Ops")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List deployed topics in tenant")
    sub.add_parser("library", help="Show available topics from library")
    sub.add_parser("sync", help="Sync state.json with tenant")

    deploy_p = sub.add_parser("deploy", help="Deploy topics from library or file")
    deploy_p.add_argument("--top", type=int, default=20, help="Deploy top N by attack count")
    deploy_p.add_argument("--names", nargs="+", help="Deploy specific topics by name")
    deploy_p.add_argument("--file", help="Load topics from a custom JSON file instead of library")

    remove_p = sub.add_parser("remove", help="Remove topics from tenant")
    remove_p.add_argument("--all", action="store_true", help="Remove all deployed topics")
    remove_p.add_argument("--name", help="Remove a specific topic by name")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        "list": cmd_list,
        "library": cmd_library,
        "deploy": cmd_deploy,
        "remove": cmd_remove,
        "sync": cmd_sync,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
