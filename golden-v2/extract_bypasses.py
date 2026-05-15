#!/usr/bin/env python3
"""
Extract successful attack prompts from AIRS Red Teaming CSV exports.

Parses the red team scan CSVs, extracts prompts that bypassed AIRS,
deduplicates by prompt text, and outputs a JSON test corpus.

Usage:
    python extract_bypasses.py
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

DOWNLOADS = Path.home() / "Downloads"

SCAN_CSVS = [
    ("652e0648-af80-4e7a-afb8-26ab232728f2", "bedrock-haiku-basic-airs"),
    ("3064640e-b736-4d7b-86dc-bacc4fc62932", "airs-defaults-static"),
    ("398e6c1e-e50d-4a07-83e2-111e2aba8a83", "unknown-static-2"),
]

OUTPUT = Path(__file__).resolve().parent / "test_attacks.json"


def parse_csv(scan_id: str, label: str) -> list[dict]:
    csv_dir = DOWNLOADS / f"AI_Red_Teaming_Report_{scan_id}"
    csv_path = csv_dir / "attacks.csv"
    if not csv_path.exists():
        print(f"[SKIP] {csv_path} not found")
        return []

    results = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("threat", "")).strip().lower() != "true":
                continue
            prompt = row.get("prompt", "").strip()
            if not prompt or len(prompt) < 10:
                continue
            results.append({
                "prompt": prompt[:9000],
                "category": row.get("category", ""),
                "sub_category": row.get("sub_category", ""),
                "severity": row.get("severity", ""),
                "scan_id": scan_id,
                "source": label,
                "multi_turn": row.get("multi_turn", "false"),
            })

    print(f"[{label}] {len(results)} successful bypasses from {csv_path.name}")
    return results


def deduplicate(attacks: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for a in attacks:
        h = hashlib.sha256(a["prompt"].encode()).hexdigest()[:16]
        if h not in seen:
            seen.add(h)
            unique.append(a)
    return unique


def main():
    all_attacks = []
    for scan_id, label in SCAN_CSVS:
        all_attacks.extend(parse_csv(scan_id, label))

    print(f"\nTotal before dedup: {len(all_attacks)}")
    unique = deduplicate(all_attacks)
    print(f"Total after dedup:  {len(unique)}")

    by_sub = {}
    for a in unique:
        sub = a["sub_category"] or "UNKNOWN"
        by_sub[sub] = by_sub.get(sub, 0) + 1

    print("\nPer sub-category:")
    for sub, count in sorted(by_sub.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}  {sub}")

    OUTPUT.write_text(json.dumps(unique, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(unique)} attacks to {OUTPUT}")


if __name__ == "__main__":
    main()
