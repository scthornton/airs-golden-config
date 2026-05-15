#!/usr/bin/env python3
"""
Test bypass prompts against an AIRS security profile via Scan API.

Loads the extracted bypass corpus, scans each prompt, computes ASR
and per-subcategory breakdown.

Usage:
    PANW_AI_SEC_API_KEY=<key> python test_runner.py
    PANW_AI_SEC_API_KEY=<key> python test_runner.py --profile golden-v2
    PANW_AI_SEC_API_KEY=<key> python test_runner.py --limit 20
"""
import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
SCAN_API = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
API_KEY = os.environ.get("PANW_AI_SEC_API_KEY", "")
DEFAULT_PROFILE = os.environ.get("PRISMA_AIRS_PROFILE", "golden-v2")
WORKERS = 8


def scan(prompt: str, profile_name: str) -> dict:
    payload = {
        "tr_id": str(uuid.uuid4()),
        "ai_profile": {"profile_name": profile_name},
        "metadata": {"app_user": "golden-v2-tester", "ai_model": "test-corpus"},
        "contents": [{"prompt": prompt[:9000]}],
    }
    try:
        r = requests.post(
            SCAN_API,
            headers={"Content-Type": "application/json", "x-pan-token": API_KEY},
            json=payload,
            timeout=30,
        )
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def run_tests(attacks: list[dict], profile: str, limit: int = 0) -> list[dict]:
    if limit:
        attacks = attacks[:limit]

    results = []
    total = len(attacks)
    print(f"\nScanning {total} prompts against profile '{profile}' ({WORKERS} workers)...")

    def scan_one(idx_attack):
        idx, attack = idx_attack
        result = scan(attack["prompt"], profile)
        action = result.get("action", "error")
        return {
            "idx": idx,
            "sub_category": attack.get("sub_category", ""),
            "category": attack.get("category", ""),
            "severity": attack.get("severity", ""),
            "action": action,
            "prompt_detected": result.get("prompt_detected", {}),
            "report_id": result.get("report_id", ""),
            "error": result.get("error", ""),
            "prompt_preview": attack["prompt"][:120],
        }

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(scan_one, (i, a)): i for i, a in enumerate(attacks)}
        done = 0
        for f in as_completed(futures):
            done += 1
            r = f.result()
            results.append(r)
            if done % 20 == 0 or done == total:
                blocked = sum(1 for x in results if x["action"] == "block")
                print(f"  [{done}/{total}] blocked: {blocked}, allowed: {done - blocked}")

    results.sort(key=lambda x: x["idx"])
    return results


def summarize(results: list[dict], profile: str) -> dict:
    total = len(results)
    blocked = sum(1 for r in results if r["action"] == "block")
    allowed = sum(1 for r in results if r["action"] == "allow")
    errors = sum(1 for r in results if r.get("error"))
    bypassed = total - blocked

    by_sub = {}
    for r in results:
        sub = r["sub_category"] or "UNKNOWN"
        if sub not in by_sub:
            by_sub[sub] = {"total": 0, "blocked": 0, "allowed": 0}
        by_sub[sub]["total"] += 1
        if r["action"] == "block":
            by_sub[sub]["blocked"] += 1
        else:
            by_sub[sub]["allowed"] += 1

    summary = {
        "profile": profile,
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "blocked": blocked,
        "allowed": allowed,
        "errors": errors,
        "asr": round(bypassed / total * 100, 2) if total else 0,
        "block_rate": round(blocked / total * 100, 2) if total else 0,
        "by_sub_category": by_sub,
    }

    print(f"\n{'='*60}")
    print(f"Profile: {profile}")
    print(f"Total: {total} | Blocked: {blocked} | Allowed (bypassed): {bypassed} | Errors: {errors}")
    print(f"ASR: {summary['asr']}% | Block Rate: {summary['block_rate']}%")
    print(f"\nPer sub-category:")
    for sub, data in sorted(by_sub.items(), key=lambda x: -x[1]["allowed"]):
        asr = data["allowed"] / data["total"] * 100 if data["total"] else 0
        marker = "!!" if asr > 10 else "  "
        print(f"  {marker} {sub:<35s} {data['blocked']:3d}/{data['total']:3d} blocked ({asr:.0f}% bypassed)")
    print(f"{'='*60}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Test bypass prompts against AIRS profile")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="AIRS profile name")
    parser.add_argument("--limit", type=int, default=0, help="Max prompts to test (0=all)")
    parser.add_argument("--attacks", default=str(ROOT / "test_attacks.json"), help="Path to attack corpus")
    args = parser.parse_args()

    if not API_KEY:
        print("[ERROR] Set PANW_AI_SEC_API_KEY environment variable")
        sys.exit(1)

    attacks = json.loads(Path(args.attacks).read_text())
    print(f"Loaded {len(attacks)} attack prompts from {args.attacks}")

    results = run_tests(attacks, args.profile, args.limit)
    summary = summarize(results, args.profile)

    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    jsonl_path = results_dir / f"results-{args.profile}-{ts}.jsonl"
    with open(jsonl_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"\nResults: {jsonl_path}")

    summary_path = results_dir / f"summary-{args.profile}-{ts}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
