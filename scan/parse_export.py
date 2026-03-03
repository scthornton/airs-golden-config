#!/usr/bin/env python3
"""
Parse red team scan exports from Strata Cloud Manager.

Handles the known data format quirks:
  - attacks.json: iteration values are JSON STRINGS (need json.loads())
  - attacks.csv: threat field is string "true"/"false", fields can be huge
  - report_summary.json: array of objects with job_type, asr, total_threats

Usage:
    python parse_export.py /path/to/exported/zip_or_dir
    python parse_export.py /path/to/attacks.json
    python parse_export.py /path/to/attacks.csv
"""

import sys
import os
import json
import csv
import zipfile
import argparse
from pathlib import Path
from collections import Counter

# Handle very large CSV fields (attack prompts can be enormous)
csv.field_size_limit(10_000_000)

RESULTS_DIR = Path(__file__).parent.parent / "results"


def parse_attacks_json(filepath: Path) -> dict:
    """Parse attacks.json — handles both formats:
      - Legacy: dict with iteration_X keys containing JSON strings
      - Current: flat list of attack objects
    """
    data = json.loads(filepath.read_text())

    all_attacks = []
    iteration_summaries = []

    if isinstance(data, list):
        # Current format: flat list of attack objects
        for attack in data:
            is_threat = attack.get("threat", False)
            all_attacks.append({
                "iteration": str(attack.get("generation", attack.get("turn", "1"))),
                "prompt": attack.get("prompt", ""),
                "response": attack.get("output", attack.get("response", "")),
                "threat": is_threat,
                "category": attack.get("category", ""),
                "sub_category": attack.get("sub_category", ""),
                "technique": attack.get("technique", ""),
                "severity": attack.get("severity", ""),
                "goal_category": attack.get("goal_category", ""),
                "multi_turn": attack.get("multi_turn", False),
            })

        total = len(all_attacks)
        threats = sum(1 for a in all_attacks if a["threat"])
        iteration_summaries.append({
            "iteration": "all",
            "total": total,
            "threats": threats,
            "asr": round(threats / total * 100, 1) if total > 0 else 0,
        })

    elif isinstance(data, dict):
        # Legacy format: iteration_X keys with JSON string values
        for key, value in data.items():
            if not key.startswith("iteration_"):
                continue

            if isinstance(value, str):
                iteration_data = json.loads(value)
            else:
                iteration_data = value

            iter_num = key.replace("iteration_", "")
            threats = 0
            total = 0

            if isinstance(iteration_data, list):
                for attack in iteration_data:
                    total += 1
                    is_threat = attack.get("threat", False)
                    if is_threat:
                        threats += 1
                    all_attacks.append({
                        "iteration": iter_num,
                        "prompt": attack.get("prompt", ""),
                        "response": attack.get("response", ""),
                        "threat": is_threat,
                        "category": attack.get("category", ""),
                        "technique": attack.get("technique", ""),
                    })

            iteration_summaries.append({
                "iteration": iter_num,
                "total": total,
                "threats": threats,
                "asr": round(threats / total * 100, 1) if total > 0 else 0,
            })

    return {
        "source": str(filepath),
        "total_attacks": len(all_attacks),
        "total_threats": sum(1 for a in all_attacks if a["threat"]),
        "asr": round(sum(1 for a in all_attacks if a["threat"]) / max(len(all_attacks), 1) * 100, 1),
        "iterations": iteration_summaries,
        "attacks": all_attacks,
    }


def parse_attacks_csv(filepath: Path) -> dict:
    """Parse attacks.csv — threat is string 'true'/'false'."""
    attacks = []

    with open(filepath, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # threat field is string "true" or "false"
            is_threat = row.get("threat", "false").strip().lower() == "true"
            attacks.append({
                "prompt": row.get("prompt", ""),
                "response": row.get("response", ""),
                "threat": is_threat,
                "category": row.get("category", ""),
                "technique": row.get("technique", ""),
                "iteration": row.get("iteration", ""),
            })

    total = len(attacks)
    threats = sum(1 for a in attacks if a["threat"])

    return {
        "source": str(filepath),
        "total_attacks": total,
        "total_threats": threats,
        "asr": round(threats / total * 100, 1) if total > 0 else 0,
        "attacks": attacks,
    }


def parse_report_summary(filepath: Path) -> dict:
    """Parse report_summary.json."""
    data = json.loads(filepath.read_text())

    # It's an array of objects
    if isinstance(data, list):
        summaries = data
    else:
        summaries = [data]

    return {
        "source": str(filepath),
        "summaries": summaries,
    }


def parse_export(path: Path) -> dict:
    """Parse a red team export (directory or zip)."""
    results = {"attacks_json": None, "attacks_csv": None, "report_summary": None}

    # Handle zip files
    if path.suffix == ".zip":
        extract_dir = path.parent / path.stem
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(extract_dir)
        path = extract_dir
        print(f"  Extracted zip to: {extract_dir}")

    if path.is_file():
        # Single file
        if path.name == "attacks.json":
            results["attacks_json"] = parse_attacks_json(path)
        elif path.name == "attacks.csv":
            results["attacks_csv"] = parse_attacks_csv(path)
        elif path.name == "report_summary.json":
            results["report_summary"] = parse_report_summary(path)
        else:
            print(f"[WARN] Unknown file type: {path.name}")
        return results

    # Directory — look for known files
    for name, parser in [
        ("attacks.json", parse_attacks_json),
        ("attacks.csv", parse_attacks_csv),
        ("report_summary.json", parse_report_summary),
    ]:
        f = path / name
        if f.exists():
            print(f"  Parsing {name}...")
            results[name.replace(".", "_")] = parser(f)

    return results


def print_summary(results: dict):
    """Print a human-readable summary of parsed results."""
    print(f"\n  {'='*50}")
    print(f"  RED TEAM EXPORT SUMMARY")
    print(f"  {'='*50}")

    for key in ["attacks_json", "attacks_csv"]:
        data = results.get(key)
        if not data:
            continue

        print(f"\n  Source: {data['source']}")
        print(f"  Total attacks:  {data['total_attacks']}")
        print(f"  Threats found:  {data['total_threats']}")
        if "asr" in data:
            print(f"  ASR:            {data['asr']}%")

        if "iterations" in data:
            print(f"\n  Per-iteration breakdown:")
            for it in data["iterations"]:
                print(f"    Iteration {it['iteration']}: {it['threats']}/{it['total']} threats ({it['asr']}% ASR)")

        # Category breakdown of successful attacks
        threat_attacks = [a for a in data.get("attacks", []) if a["threat"]]
        if threat_attacks:
            cats = Counter(a.get("category", "unknown") for a in threat_attacks)
            print(f"\n  Threat categories:")
            for cat, count in cats.most_common(15):
                print(f"    {count:>5}  {cat}")

            techs = Counter(a.get("technique", "unknown") for a in threat_attacks)
            print(f"\n  Top techniques:")
            for tech, count in techs.most_common(10):
                print(f"    {count:>5}  {tech}")

    summary = results.get("report_summary")
    if summary:
        print(f"\n  Report Summary ({summary['source']}):")
        for s in summary.get("summaries", []):
            print(f"    Job: {s.get('job_type', '?')}  ASR: {s.get('asr', '?')}%  Threats: {s.get('total_threats', '?')}")

    print(f"  {'='*50}")


def save_parsed(results: dict, iteration: int = None):
    """Save parsed results to the iteration directory."""
    if iteration is None:
        existing = sorted(RESULTS_DIR.glob("iteration_*"))
        iteration = len(existing) + 1

    iter_dir = RESULTS_DIR / f"iteration_{iteration:02d}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    out_file = iter_dir / "parsed_export.json"

    # Strip full attack text for the saved summary (can be huge)
    save_data = {}
    for key in ["attacks_json", "attacks_csv"]:
        data = results.get(key)
        if not data:
            continue
        save_data[key] = {
            "source": data["source"],
            "total_attacks": data["total_attacks"],
            "total_threats": data["total_threats"],
        }
        if "asr" in data:
            save_data[key]["asr"] = data["asr"]
        if "iterations" in data:
            save_data[key]["iterations"] = data["iterations"]
        # Save only threat prompts (not all prompts — too large)
        save_data[key]["threat_prompts"] = [
            {"prompt": a["prompt"][:500], "category": a.get("category", ""), "technique": a.get("technique", "")}
            for a in data.get("attacks", []) if a["threat"]
        ]

    if results.get("report_summary"):
        save_data["report_summary"] = results["report_summary"]

    out_file.write_text(json.dumps(save_data, indent=2))
    print(f"\n  Parsed results saved: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Golden Config — Parse Red Team Export")
    parser.add_argument("path", help="Path to export zip, directory, or file")
    parser.add_argument("--iteration", type=int, help="Iteration number for output dir")
    parser.add_argument("--no-save", action="store_true", help="Don't save parsed results")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[ERROR] Path not found: {args.path}")
        sys.exit(1)

    results = parse_export(path)
    print_summary(results)

    if not args.no_save:
        save_parsed(results, iteration=args.iteration)


if __name__ == "__main__":
    main()
