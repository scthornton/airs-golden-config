#!/usr/bin/env python3
"""
Gap Analysis — identify config gaps from scan/red-team results.

Cross-references successful attacks against deployed topics and built-in
detectors to recommend config changes.

Usage:
    python gap_analysis.py results/iteration_01/scan_results.json
    python gap_analysis.py results/iteration_01/parsed_export.json
    python gap_analysis.py results/iteration_01/             # Auto-detect files
"""

import sys
import os
import json
import argparse
from pathlib import Path
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mgmt"))
from config import load_state

TOPIC_LIB = Path(__file__).parent.parent.parent / "prisma-airs-custom-topics" / "topics"

# AIRS built-in detectors (not custom topics)
BUILTIN_DETECTORS = {
    "prompt-injection": "Detects instruction injection attempts",
    "jailbreak": "Detects jailbreak attempts (DAN, developer mode, etc.)",
    "dlp-sensitive-content": "Detects sensitive data leakage (PII, credentials, etc.)",
    "malicious-url": "Detects malicious URLs in prompts/responses",
}

# Mapping from red team categories to topic names
CATEGORY_TO_TOPIC = {
    "SYSTEM_PROMPT_LEAK": "system_prompt_disclosure",
    "TOOL_LEAK": "tool_capability_enumeration",
    "JAILBREAK": "instruction_override_injection",
    "PROMPT_INJECTION": "instruction_override_injection",
    "HARMFUL_CONTENT": "violence_harm_instructions",
    "CBRN": "cbrn_weapons_content",
    "WEAPONS": "weapons_manufacturing",
    "DRUGS": "drug_synthesis_manufacturing",
    "MALWARE": "malicious_code_generation",
    "HACKING": "hacking_system_intrusion",
    "HATE_SPEECH": "hate_speech_discrimination",
    "DISCRIMINATION": "racial_stereotyping_content",
    "SEXUAL_CONTENT": "sexual_exploitation_content",
    "POLITICAL": "political_manipulation",
    "SELF_HARM": "self_harm_concealment",
    "FORGERY": "document_identity_forgery",
    "PII": "pii_harvesting_identity_theft",
    "COMPETITOR": "competitor_intelligence",
    "BRAND": "brand_reputation_attacks",
    "DATA_PRIVACY": "cross_client_data_privacy",
    "FINANCIAL": "investment_advice_recommendations",
    "MEDICAL": "medical_diagnosis_treatment",
    "LEGAL": "legal_counsel_advice",
}


def load_topic_library() -> dict:
    """Load all topics from the library, keyed by topic_name."""
    topics = {}
    if not TOPIC_LIB.exists():
        return topics

    for f in sorted(TOPIC_LIB.glob("*.json")):
        data = json.loads(f.read_text())
        category = data.get("category", f.stem)
        for topic in data.get("topics", []):
            name = topic["topic_name"]
            topic["_category"] = category
            topics[name] = topic

    return topics


def analyze_scan_results(filepath: Path) -> list[dict]:
    """Extract allowed (unblocked) prompts from scan_results.json."""
    data = json.loads(filepath.read_text())
    results = data.get("results", [])
    return [r for r in results if r.get("action") != "block" and r.get("action") != "error"]


def analyze_parsed_export(filepath: Path) -> list[dict]:
    """Extract successful attacks from parsed_export.json."""
    data = json.loads(filepath.read_text())
    threats = []

    for key in ["attacks_json", "attacks_csv"]:
        section = data.get(key, {})
        for t in section.get("threat_prompts", []):
            threats.append(t)

    return threats


def run_gap_analysis(allowed: list[dict], deployed_topics: list[str], library: dict) -> dict:
    """Identify gaps between what's deployed and what's needed."""

    # Categorize allowed prompts by attack type
    attack_categories = Counter()
    uncategorized = []

    for item in allowed:
        prompt = item.get("prompt", "")[:200].lower()
        category = item.get("category", "")

        # Try to match to a known category
        matched = False
        for cat_key, topic_name in CATEGORY_TO_TOPIC.items():
            if cat_key.lower() in category.lower() or cat_key.lower().replace("_", " ") in prompt:
                attack_categories[topic_name] += 1
                matched = True
                break

        # Heuristic matching for common attack patterns
        if not matched:
            if any(kw in prompt for kw in ["ignore", "override", "dan ", "developer mode", "jailbreak"]):
                attack_categories["instruction_override_injection"] += 1
            elif any(kw in prompt for kw in ["system prompt", "instructions", "rules"]):
                attack_categories["system_prompt_disclosure"] += 1
            elif any(kw in prompt for kw in ["tools", "api", "endpoint", "function"]):
                attack_categories["tool_capability_enumeration"] += 1
            elif any(kw in prompt for kw in ["bomb", "weapon", "explosive", "gun"]):
                attack_categories["weapons_manufacturing"] += 1
            elif any(kw in prompt for kw in ["malware", "virus", "trojan", "ransomware"]):
                attack_categories["malicious_code_generation"] += 1
            elif any(kw in prompt for kw in ["hack", "exploit", "vulnerability"]):
                attack_categories["hacking_system_intrusion"] += 1
            else:
                uncategorized.append(item)

    # Determine which topics would help
    recommendations = []
    for topic_name, count in attack_categories.most_common():
        is_deployed = topic_name in deployed_topics
        in_library = topic_name in library
        priority = library.get(topic_name, {}).get("priority", "unknown")
        attacks = library.get(topic_name, {}).get("red_team_data", {}).get("successful_attacks", 0)

        recommendations.append({
            "topic_name": topic_name,
            "matched_attacks": count,
            "deployed": is_deployed,
            "in_library": in_library,
            "priority": priority,
            "historical_attacks": attacks,
            "action": "already deployed" if is_deployed else ("deploy" if in_library else "create new"),
        })

    # Sort: undeployed first, then by matched_attacks
    recommendations.sort(key=lambda r: (r["deployed"], -r["matched_attacks"]))

    return {
        "total_allowed": len(allowed),
        "categorized": sum(attack_categories.values()),
        "uncategorized": len(uncategorized),
        "recommendations": recommendations,
        "uncategorized_prompts": [
            item.get("prompt", "")[:200] for item in uncategorized[:20]
        ],
    }


def print_gap_report(analysis: dict):
    """Print human-readable gap analysis."""
    print(f"\n  {'='*60}")
    print(f"  GAP ANALYSIS REPORT")
    print(f"  {'='*60}")
    print(f"  Total allowed/threats: {analysis['total_allowed']}")
    print(f"  Categorized:           {analysis['categorized']}")
    print(f"  Uncategorized:         {analysis['uncategorized']}")

    recs = analysis["recommendations"]
    if recs:
        print(f"\n  RECOMMENDATIONS:")
        print(f"  {'Action':<18} {'Priority':<10} {'Matches':>8} {'Historical':>10}  Topic")
        print(f"  {'─'*18} {'─'*10} {'─'*8} {'─'*10}  {'─'*30}")
        for r in recs:
            print(
                f"  {r['action']:<18} {r['priority']:<10} {r['matched_attacks']:>8} "
                f"{r['historical_attacks']:>10}  {r['topic_name']}"
            )

    uncat = analysis.get("uncategorized_prompts", [])
    if uncat:
        print(f"\n  UNCATEGORIZED PROMPTS (may need new topics):")
        for p in uncat:
            print(f"    - {p}")

    # Deployment capacity check
    state = load_state()
    deployed_count = len(state.get("deployed_topics", []))
    to_deploy = [r for r in recs if r["action"] == "deploy"]
    total_after = deployed_count + len(to_deploy)

    print(f"\n  DEPLOYMENT CAPACITY:")
    print(f"  Currently deployed: {deployed_count}/20")
    print(f"  Recommended to add: {len(to_deploy)}")
    print(f"  Total after deploy: {total_after}/20")
    if total_after > 20:
        print(f"  WARNING: Exceeds 20-topic limit! Prioritize tier-1 topics.")

    print(f"  {'='*60}")


def save_gap_report(analysis: dict, iteration: int = None):
    """Save gap report as markdown."""
    results_dir = Path(__file__).parent.parent / "results"
    if iteration is None:
        existing = sorted(results_dir.glob("iteration_*"))
        iteration = len(existing) or 1

    iter_dir = results_dir / f"iteration_{iteration:02d}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    out_file = iter_dir / "gap_report.md"

    lines = [
        f"# Gap Analysis — Iteration {iteration}",
        "",
        f"**Allowed/Threats:** {analysis['total_allowed']}",
        f"**Categorized:** {analysis['categorized']}",
        f"**Uncategorized:** {analysis['uncategorized']}",
        "",
        "## Recommendations",
        "",
        "| Action | Priority | Matches | Historical | Topic |",
        "|--------|----------|---------|------------|-------|",
    ]
    for r in analysis["recommendations"]:
        lines.append(
            f"| {r['action']} | {r['priority']} | {r['matched_attacks']} "
            f"| {r['historical_attacks']} | {r['topic_name']} |"
        )

    uncat = analysis.get("uncategorized_prompts", [])
    if uncat:
        lines.extend(["", "## Uncategorized Prompts", ""])
        for p in uncat:
            lines.append(f"- `{p}`")

    out_file.write_text("\n".join(lines) + "\n")
    print(f"\n  Gap report saved: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Golden Config — Gap Analysis")
    parser.add_argument("path", help="Path to scan_results.json, parsed_export.json, or iteration dir")
    parser.add_argument("--iteration", type=int, help="Iteration number for output")
    parser.add_argument("--no-save", action="store_true", help="Don't save gap report")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[ERROR] Path not found: {args.path}")
        sys.exit(1)

    # Load the topic library and current deployment state
    library = load_topic_library()
    state = load_state()
    deployed_topics = state.get("deployed_topics", [])

    print(f"  Topic library: {len(library)} topics")
    print(f"  Deployed:      {len(deployed_topics)} topics")

    # Determine input type and extract allowed/threat prompts
    allowed = []
    if path.is_dir():
        # Try both files in the directory
        scan_file = path / "scan_results.json"
        export_file = path / "parsed_export.json"
        if scan_file.exists():
            allowed.extend(analyze_scan_results(scan_file))
        if export_file.exists():
            allowed.extend(analyze_parsed_export(export_file))
    elif "scan_results" in path.name:
        allowed = analyze_scan_results(path)
    elif "parsed_export" in path.name:
        allowed = analyze_parsed_export(path)
    else:
        print(f"[ERROR] Unrecognized file: {path.name}")
        print(f"  Expected: scan_results.json or parsed_export.json")
        sys.exit(1)

    if not allowed:
        print(f"\n  No allowed/threat prompts found — config may already be optimal!")
        return

    # Run analysis
    analysis = run_gap_analysis(allowed, deployed_topics, library)
    print_gap_report(analysis)

    if not args.no_save:
        save_gap_report(analysis, iteration=args.iteration)


if __name__ == "__main__":
    main()
