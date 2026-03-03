#!/usr/bin/env python3
"""
Golden Config — Report Generator

Generates iteration reports, experiment logs, and final summary from
existing data files (scan_results.json, parsed_export.json, vm_logs.json,
gap_report.md, state.json).

Subcommands:
    python report/generate_report.py iteration 0    # Per-iteration report
    python report/generate_report.py log             # Rebuild master experiment log
    python report/generate_report.py summary         # Quick status to stdout
    python report/generate_report.py final           # Publishable final report
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mgmt"))
from config import load_state

BASE_DIR = Path(__file__).parent.parent
RESULTS_DIR = BASE_DIR / "results"
DOCS_DIR = BASE_DIR / "docs"

# Experiment metadata
EXPERIMENT = {
    "goal": "0% ASR on AIRS red team scans",
    "target_vm": "golden-config-vertex",
    "target_ip": "136.115.78.7:5008",
    "profile": "redteamtest",
    "llm": "gpt-4o-mini",
    "start_date": "2026-03-01",
    "topic_library_size": 27,
    "topic_categories": 7,
}


# ── Data loading helpers ─────────────────────────────────────────────────────

def load_iteration_data(iteration: int) -> dict:
    """Load all available data files for an iteration."""
    iter_dir = RESULTS_DIR / f"iteration_{iteration:02d}"
    if not iter_dir.exists():
        print(f"[ERROR] Iteration directory not found: {iter_dir}")
        sys.exit(1)

    data = {"iteration": iteration, "dir": iter_dir}

    # scan_results.json
    scan_file = iter_dir / "scan_results.json"
    if scan_file.exists():
        data["scan_results"] = json.loads(scan_file.read_text())

    # parsed_export.json
    export_file = iter_dir / "parsed_export.json"
    if export_file.exists():
        data["parsed_export"] = json.loads(export_file.read_text())

    # vm_logs.json
    vm_file = iter_dir / "vm_logs.json"
    if vm_file.exists():
        data["vm_logs"] = json.loads(vm_file.read_text())

    # gap_report.md
    gap_file = iter_dir / "gap_report.md"
    if gap_file.exists():
        data["gap_report"] = gap_file.read_text()

    return data


def list_iterations() -> list[int]:
    """List all iteration numbers that have data."""
    iterations = []
    for d in sorted(RESULTS_DIR.glob("iteration_*")):
        if d.is_dir():
            try:
                num = int(d.name.split("_")[1])
                iterations.append(num)
            except (IndexError, ValueError):
                pass
    return iterations


def get_state_config(state: dict) -> list[tuple[str, str]]:
    """Build the configuration table from state."""
    deployed = state.get("deployed_topics", [])
    rows = [
        ("Built-in: prompt-injection", "BLOCK"),
        ("Built-in: jailbreak", "BLOCK"),
        ("Built-in: DLP", "BLOCK"),
        ("Built-in: toxic-content", "BLOCK"),
        ("Built-in: malicious-code", "BLOCK"),
        ("Built-in: URL categories", "BLOCK"),
        ("Custom topics deployed", f"{len(deployed)} / 20"),
        ("Timeout action", "BLOCK (20s)"),
    ]
    return rows


# ── Subcommand: iteration ────────────────────────────────────────────────────

def cmd_iteration(args):
    """Generate a per-iteration report."""
    iteration = args.iteration_num
    data = load_iteration_data(iteration)
    state = load_state()

    lines = []
    lines.append(f"# Golden Config — Iteration {iteration} Report")
    lines.append("")

    # Date from scan_results or vm_logs
    date = "—"
    scan = data.get("scan_results")
    if scan:
        date = scan.get("timestamp", "")[:10]
    elif data.get("vm_logs"):
        date = data["vm_logs"].get("collected_at", "")[:10]

    lines.append(f"**Date:** {date}  |  **Profile:** {state.get('profile_name', '?')}  |  **Iteration:** {iteration}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Executive Summary ──
    lines.append("## Executive Summary")
    lines.append("")

    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")

    vm = data.get("vm_logs", {}).get("summary", {})
    if vm:
        total_blocked = vm.get("prompt_blocked", 0) + vm.get("response_blocked", 0)
        total_scans = vm.get("prompt_scans", 0)
        allowed = vm.get("allowed_through", 0)
        block_pct = vm.get("block_rate_percent", 0)
        lines.append(f"| VM Prompt Scans | {total_scans} |")
        lines.append(f"| Prompt Blocked | {vm.get('prompt_blocked', 0)} ({round(vm.get('prompt_blocked', 0) / max(total_scans, 1) * 100, 1)}%) |")
        lines.append(f"| Response Blocked | {vm.get('response_blocked', 0)} |")
        lines.append(f"| Allowed Through | {allowed} ({round(allowed / max(total_scans, 1) * 100, 1)}%) |")
        lines.append(f"| **VM Block Rate** | **{block_pct}%** |")

    if scan:
        s = scan.get("summary", {})
        lines.append(f"| Local Scan Total | {s.get('total', 0)} |")
        lines.append(f"| Local Scan Blocked | {s.get('blocked', 0)} |")
        lines.append(f"| Local Scan Allowed | {s.get('allowed', 0)} |")
        lines.append(f"| **Local Detection Rate** | **{s.get('detection_rate_percent', 0)}%** |")

    export = data.get("parsed_export")
    if export:
        for key in ["attacks_json", "attacks_csv"]:
            section = export.get(key)
            if section:
                lines.append(f"| SCM Export ({key}) Total | {section.get('total_attacks', '—')} |")
                lines.append(f"| SCM Export ({key}) Threats | {section.get('total_threats', '—')} |")
                if "asr" in section:
                    lines.append(f"| **SCM ASR ({key})** | **{section['asr']}%** |")

    lines.append("")

    # ── Configuration ──
    lines.append("### Configuration")
    lines.append("")
    lines.append("| Component | Setting |")
    lines.append("|-----------|---------|")
    for component, setting in get_state_config(state):
        lines.append(f"| {component} | {setting} |")

    deployed = state.get("deployed_topics", [])
    if deployed:
        lines.append("")
        lines.append("**Deployed topics:** " + ", ".join(f"`{t}`" for t in deployed))
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Detector Performance ──
    vm_data = data.get("vm_logs", {})
    det = vm_data.get("detector_breakdown", {})
    if det:
        lines.append("## AIRS Detector Performance")
        lines.append("")
        total_firings = sum(det.values())
        lines.append("| Detector | Times Fired | % of Total |")
        lines.append("|----------|-------------|------------|")
        for name, count in sorted(det.items(), key=lambda x: -x[1]):
            pct = round(count / max(total_firings, 1) * 100, 1)
            lines.append(f"| {name} | {count} | {pct}% |")
        lines.append("")

    # ── Blocked Attack Samples ──
    timeline = vm_data.get("timeline", [])
    blocked_events = [e for e in timeline if e.get("event") == "prompt_blocked"]
    if blocked_events:
        lines.append("## Blocked Attack Samples")
        lines.append("")
        lines.append("| # | Prompt Preview |")
        lines.append("|---|---------------|")
        for i, e in enumerate(blocked_events[:15]):
            preview = e.get("prompt_preview", "")[:120].replace("|", "\\|")
            lines.append(f"| {i+1} | {preview} |")
        if len(blocked_events) > 15:
            lines.append(f"| ... | *{len(blocked_events) - 15} more blocked prompts* |")
        lines.append("")

    # ── Allowed Attack Samples ──
    if scan:
        allowed_prompts = [
            r for r in scan.get("results", [])
            if r.get("action") not in ("block", "error")
            and r.get("source") != "builtin"
            or (r.get("action") not in ("block", "error") and r.get("source") == "builtin"
                and r.get("category") != "benign")
        ]
        # Actually: show all allowed that aren't obviously benign
        allowed_prompts = [
            r for r in scan.get("results", [])
            if r.get("action") not in ("block", "error")
        ]
        if allowed_prompts:
            lines.append("## Allowed Prompts (Gaps)")
            lines.append("")
            lines.append("| # | Label | Prompt | Detectors |")
            lines.append("|---|-------|--------|-----------|")
            for i, r in enumerate(allowed_prompts):
                prompt = r.get("prompt", "")[:100].replace("|", "\\|")
                det_info = r.get("prompt_detected", {})
                fired = [k for k, v in det_info.items() if v]
                det_str = ", ".join(fired) if fired else "none"
                lines.append(f"| {i+1} | {r.get('label', '')} | {prompt} | {det_str} |")
            lines.append("")

    # ── Local Scan Results ──
    if scan:
        lines.append("## Local Scan Results")
        lines.append("")
        s = scan.get("summary", {})
        lines.append(f"- **Total:** {s.get('total', 0)}")
        lines.append(f"- **Blocked:** {s.get('blocked', 0)} ({s.get('detection_rate_percent', 0)}%)")
        lines.append(f"- **Allowed:** {s.get('allowed', 0)} ({s.get('asr_percent', 0)}%)")
        lines.append(f"- **Errors:** {s.get('errors', 0)}")
        lines.append("")

    # ── SCM Red Team Results ──
    if export:
        lines.append("## SCM Red Team Results")
        lines.append("")
        for key in ["attacks_json", "attacks_csv"]:
            section = export.get(key)
            if not section:
                continue
            lines.append(f"### {key}")
            lines.append(f"- **Source:** {section.get('source', '—')}")
            lines.append(f"- **Total attacks:** {section.get('total_attacks', 0)}")
            lines.append(f"- **Threats:** {section.get('total_threats', 0)}")
            if "asr" in section:
                lines.append(f"- **ASR:** {section['asr']}%")
            iters = section.get("iterations", [])
            if iters:
                lines.append("")
                lines.append("| Iteration | Total | Threats | ASR |")
                lines.append("|-----------|-------|---------|-----|")
                for it in iters:
                    lines.append(f"| {it['iteration']} | {it['total']} | {it['threats']} | {it['asr']}% |")
            lines.append("")

    # ── Gap Analysis ──
    gap = data.get("gap_report")
    if gap:
        lines.append("## Gap Analysis")
        lines.append("")
        # Inline the gap report content (skip the title line)
        gap_lines = gap.strip().splitlines()
        for gl in gap_lines:
            if gl.startswith("# "):
                continue  # Skip top-level heading (already have section header)
            lines.append(gl)
        lines.append("")

    # ── Comparison vs Previous ──
    if iteration > 0:
        prev_dir = RESULTS_DIR / f"iteration_{iteration - 1:02d}"
        if prev_dir.exists():
            prev_data = load_iteration_data(iteration - 1)
            lines.append("## Comparison vs Previous Iteration")
            lines.append("")
            lines.append(f"| Metric | Iter {iteration - 1} | Iter {iteration} | Delta |")
            lines.append("|--------|---------|---------|-------|")

            # Local scan comparison
            prev_scan = prev_data.get("scan_results", {}).get("summary", {})
            curr_scan = scan.get("summary", {}) if scan else {}
            if prev_scan and curr_scan:
                prev_dr = prev_scan.get("detection_rate_percent", 0)
                curr_dr = curr_scan.get("detection_rate_percent", 0)
                delta_dr = round(curr_dr - prev_dr, 1)
                sign = "+" if delta_dr > 0 else ""
                lines.append(f"| Local detection rate | {prev_dr}% | {curr_dr}% | {sign}{delta_dr}% |")

            # VM log comparison
            prev_vm = prev_data.get("vm_logs", {}).get("summary", {})
            curr_vm = vm
            if prev_vm and curr_vm:
                prev_br = prev_vm.get("block_rate_percent", 0)
                curr_br = curr_vm.get("block_rate_percent", 0)
                delta_br = round(curr_br - prev_br, 1)
                sign = "+" if delta_br > 0 else ""
                lines.append(f"| VM block rate | {prev_br}% | {curr_br}% | {sign}{delta_br}% |")

            # Topic count
            lines.append(f"| Custom topics | {len(prev_data.get('scan_results', {}).get('results', []))} scanned | {len(scan.get('results', [])) if scan else '—'} scanned | — |")
            lines.append("")

    # ── Next Steps ──
    lines.append("## Next Steps")
    lines.append("")
    if gap:
        # Extract recommendations from gap report
        in_recs = False
        for gl in gap.strip().splitlines():
            if "deploy" in gl.lower() and "|" in gl and "Action" not in gl and "---" not in gl:
                parts = [p.strip() for p in gl.split("|") if p.strip()]
                if parts and parts[0] == "deploy":
                    topic = parts[-1] if len(parts) >= 5 else parts[-1]
                    lines.append(f"- [ ] Deploy topic: `{topic}`")
        lines.append("- [ ] Re-run red team scan after deploying new topics")
        lines.append("- [ ] Collect VM logs for next iteration")
    else:
        lines.append("- [ ] Run gap analysis on this iteration's results")
        lines.append("- [ ] Deploy recommended topics")

    lines.append("")

    # Write the report
    out_file = data["dir"] / "iteration_report.md"
    out_file.write_text("\n".join(lines) + "\n")
    print(f"\n  Iteration report saved: {out_file}")
    print(f"  Lines: {len(lines)}")


# ── Subcommand: log ──────────────────────────────────────────────────────────

def cmd_log(args):
    """Rebuild the master experiment log from all iteration data."""
    iterations = list_iterations()
    if not iterations:
        print("[WARN] No iterations found.")
        return

    state = load_state()

    lines = []
    lines.append("# Golden Config — Experiment Log")
    lines.append("")

    # Experiment parameters
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    # Proper label formatting (preserve acronyms)
    LABEL_MAP = {
        "goal": "Goal",
        "target_vm": "Target VM",
        "target_ip": "Target IP",
        "profile": "Profile",
        "llm": "LLM",
        "start_date": "Start Date",
        "topic_library_size": "Topic Library Size",
        "topic_categories": "Topic Categories",
    }
    for key, val in EXPERIMENT.items():
        label = LABEL_MAP.get(key, key.replace("_", " ").title())
        lines.append(f"| {label} | {val} |")
    lines.append(f"| Current Iteration | {state.get('iteration', '?')} |")
    lines.append(f"| Topics Deployed | {len(state.get('deployed_topics', []))} / 20 |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-iteration summaries
    for iteration in iterations:
        data = load_iteration_data(iteration)

        # Determine iteration label
        if iteration == 0:
            label = "Baseline"
        else:
            label = f"Topic Deployment #{iteration}"

        # Date
        date = "—"
        scan = data.get("scan_results")
        if scan:
            date = scan.get("timestamp", "")[:10]

        lines.append(f"## Iteration {iteration} — {label} ({date})")
        lines.append("")

        # Config snapshot
        deployed = state.get("deployed_topics", [])
        lines.append(f"**Config:** Built-in detectors + {len(deployed)} custom topics")
        lines.append("")

        # Results table
        lines.append("| Source | Total | Blocked | Allowed | Rate |")
        lines.append("|--------|-------|---------|---------|------|")

        if scan:
            s = scan.get("summary", {})
            lines.append(
                f"| Local scan | {s.get('total', '—')} | {s.get('blocked', '—')} "
                f"| {s.get('allowed', '—')} | {s.get('detection_rate_percent', '—')}% |"
            )

        vm = data.get("vm_logs", {}).get("summary", {})
        if vm:
            total_blocked = vm.get("prompt_blocked", 0) + vm.get("response_blocked", 0)
            lines.append(
                f"| VM logs | {vm.get('prompt_scans', '—')} | {total_blocked} "
                f"| {vm.get('allowed_through', '—')} | {vm.get('block_rate_percent', '—')}% |"
            )

        export = data.get("parsed_export")
        if export:
            for key in ["attacks_json", "attacks_csv"]:
                section = export.get(key)
                if section:
                    lines.append(
                        f"| SCM {key} | {section.get('total_attacks', '—')} "
                        f"| — | {section.get('total_threats', '—')} threats "
                        f"| {section.get('asr', '—')}% ASR |"
                    )
        else:
            lines.append("| SCM export | — | — | — | — |")

        lines.append("")

        # Gaps identified
        gap = data.get("gap_report", "")
        if gap:
            # Extract topic names from gap report recommendations
            topics_to_deploy = []
            for gl in gap.splitlines():
                if "| deploy" in gl.lower():
                    parts = [p.strip() for p in gl.split("|") if p.strip()]
                    if parts and len(parts) >= 5:
                        topics_to_deploy.append(parts[-1])
            if topics_to_deploy:
                lines.append(f"**Gaps identified:** {', '.join(topics_to_deploy)}")
            else:
                lines.append("**Gaps identified:** See gap report")
        else:
            lines.append("**Gaps identified:** Not yet analyzed")

        lines.append("")
        lines.append("---")
        lines.append("")

    # Write
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DOCS_DIR / "experiment_log.md"
    out_file.write_text("\n".join(lines) + "\n")
    print(f"\n  Experiment log saved: {out_file}")
    print(f"  Iterations covered: {len(iterations)}")


# ── Subcommand: summary ─────────────────────────────────────────────────────

def cmd_summary(args):
    """Print quick status to stdout."""
    state = load_state()
    iterations = list_iterations()
    latest = max(iterations) if iterations else None

    print()
    print("Golden Config — Current State")
    print("══════════════════════════════")
    print(f"Profile:   {state.get('profile_name', '?')} ({state.get('profile_id', '?')[:12]}...)")
    print(f"Iteration: {state.get('iteration', '?')}")
    print(f"Topics:    {len(state.get('deployed_topics', []))} / 20 deployed")
    print(f"VM:        {EXPERIMENT['target_ip']} (BLOCKING)")

    if latest is not None:
        data = load_iteration_data(latest)

        print(f"\nLast results (iteration_{latest:02d}):")

        scan = data.get("scan_results", {}).get("summary", {})
        if scan:
            print(f"  Local scan: {scan.get('detection_rate_percent', '?')}% block rate ({scan.get('blocked', '?')}/{scan.get('total', '?')})")

        vm = data.get("vm_logs", {}).get("summary", {})
        if vm:
            total_blocked = vm.get("prompt_blocked", 0) + vm.get("response_blocked", 0)
            print(f"  VM logs:    {vm.get('block_rate_percent', '?')}% block rate ({total_blocked}/{vm.get('prompt_scans', '?')})")

        export = data.get("parsed_export")
        if export:
            for key in ["attacks_json", "attacks_csv"]:
                section = export.get(key)
                if section and "asr" in section:
                    print(f"  SCM {key}: {section['asr']}% ASR ({section.get('total_threats', '?')} threats / {section.get('total_attacks', '?')} total)")

        gap = data.get("gap_report", "")
        if gap:
            deploy_count = gap.lower().count("| deploy")
            print(f"  Gaps:       {deploy_count} topic(s) recommended")
        else:
            print(f"  Gaps:       Not yet analyzed")

    deployed = state.get("deployed_topics", [])
    if deployed:
        print(f"\nDeployed topics:")
        for t in deployed:
            print(f"  - {t}")

    print()


# ── Subcommand: final ────────────────────────────────────────────────────────

def cmd_final(args):
    """Generate the publishable final report."""
    iterations = list_iterations()
    if not iterations:
        print("[ERROR] No iterations found.")
        sys.exit(1)

    state = load_state()

    lines = []
    lines.append("# Golden Config — Final Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Executive Summary ──
    lines.append("## Executive Summary")
    lines.append("")

    # Starting and ending ASR
    first_data = load_iteration_data(iterations[0])
    last_data = load_iteration_data(iterations[-1])

    first_scan = first_data.get("scan_results", {}).get("summary", {})
    last_scan = last_data.get("scan_results", {}).get("summary", {})

    start_dr = first_scan.get("detection_rate_percent", "?")
    end_dr = last_scan.get("detection_rate_percent", "?")
    start_asr = first_scan.get("asr_percent", "?")
    end_asr = last_scan.get("asr_percent", "?")

    lines.append(f"This experiment iteratively tuned a Palo Alto Networks Prisma AIRS security profile")
    lines.append(f"to achieve a 0% Attack Success Rate (ASR) against red team scans.")
    lines.append("")
    lines.append("| Metric | Start (Iter 0) | End (Iter {}) |".format(iterations[-1]))
    lines.append("|--------|----------------|---------------|")
    lines.append(f"| Local scan detection rate | {start_dr}% | {end_dr}% |")
    lines.append(f"| Local scan ASR | {start_asr}% | {end_asr}% |")

    first_vm = first_data.get("vm_logs", {}).get("summary", {})
    last_vm = last_data.get("vm_logs", {}).get("summary", {})
    if first_vm:
        lines.append(f"| VM block rate | {first_vm.get('block_rate_percent', '?')}% | {last_vm.get('block_rate_percent', '?')}% |")

    lines.append(f"| Custom topics | 0 | {len(state.get('deployed_topics', []))} |")
    lines.append(f"| Total iterations | — | {len(iterations)} |")
    lines.append("")

    # ── Methodology ──
    lines.append("## Methodology")
    lines.append("")
    lines.append("### Architecture")
    lines.append("")
    lines.append("```")
    lines.append("Red Team Scanner (SCM)")
    lines.append("        │")
    lines.append("        ▼")
    lines.append("┌─────────────────────┐")
    lines.append("│  AIRS Hard-Block    │")
    lines.append("│  Wrapper (Flask)    │")
    lines.append("│                     │")
    lines.append("│  1. Prompt scan ────┼──► AIRS Scan API")
    lines.append("│  2. If BLOCK → stop │")
    lines.append("│  3. LLM call ───────┼──► OpenAI API")
    lines.append("│  4. Response scan ──┼──► AIRS Scan API")
    lines.append("│  5. If BLOCK → stop │")
    lines.append("│  6. Return response │")
    lines.append("└─────────────────────┘")
    lines.append("```")
    lines.append("")
    lines.append("### Tools")
    lines.append("")
    lines.append(f"- **Target VM:** {EXPERIMENT['target_vm']} ({EXPERIMENT['target_ip']})")
    lines.append(f"- **LLM:** {EXPERIMENT['llm']}")
    lines.append(f"- **Security Profile:** {EXPERIMENT['profile']}")
    lines.append(f"- **Scan API:** service.api.aisecurity.paloaltonetworks.com")
    lines.append(f"- **Management API:** api.sase.paloaltonetworks.com/aisec")
    lines.append("")
    lines.append("### Process")
    lines.append("")
    lines.append("Each iteration followed this loop:")
    lines.append("")
    lines.append("1. Run red team scan from SCM against the wrapper VM")
    lines.append("2. Export results from SCM")
    lines.append("3. Parse export data (`parse_export.py`)")
    lines.append("4. Collect VM logs (`collect_vm_logs.py`)")
    lines.append("5. Run gap analysis (`gap_analysis.py`)")
    lines.append("6. Deploy recommended custom topics via Management API")
    lines.append("7. Repeat until 0% ASR")
    lines.append("")

    # ── Iteration Summary Table ──
    lines.append("## Iteration Summary")
    lines.append("")
    lines.append("| Iter | Date | Topics | Local DR | Local ASR | VM Block Rate | Action |")
    lines.append("|------|------|--------|----------|-----------|---------------|--------|")

    for iteration in iterations:
        data = load_iteration_data(iteration)
        scan = data.get("scan_results", {})
        s = scan.get("summary", {})
        vm = data.get("vm_logs", {}).get("summary", {})

        date = scan.get("timestamp", "")[:10] or "—"
        dr = s.get("detection_rate_percent", "—")
        asr = s.get("asr_percent", "—")
        br = vm.get("block_rate_percent", "—") if vm else "—"

        # Determine action taken
        gap = data.get("gap_report", "")
        deploy_count = gap.lower().count("| deploy") if gap else 0
        action = f"Deploy {deploy_count} topics" if deploy_count > 0 else "Baseline" if iteration == 0 else "—"

        lines.append(f"| {iteration} | {date} | {len(state.get('deployed_topics', []))} | {dr}% | {asr}% | {br}% | {action} |")

    lines.append("")

    # ── ASR Progression ──
    lines.append("## ASR Progression")
    lines.append("")
    lines.append("```")
    lines.append("ASR %")
    lines.append("100 ┤")

    for iteration in iterations:
        data = load_iteration_data(iteration)
        s = data.get("scan_results", {}).get("summary", {})
        asr = s.get("asr_percent", 0)
        bar_len = int(asr / 2)  # Scale to ~50 chars width
        bar = "█" * bar_len
        lines.append(f"  {iteration:>2} ┤ {bar} {asr}%")

    lines.append("  0 ┤ ← TARGET")
    lines.append("    └" + "─" * 50)
    lines.append("      Iteration →")
    lines.append("```")
    lines.append("")

    # ── Final Configuration ──
    lines.append("## Final Configuration")
    lines.append("")
    lines.append("### Built-in Detectors")
    lines.append("")
    lines.append("| Detector | Action |")
    lines.append("|----------|--------|")
    for component, setting in get_state_config(state):
        if component.startswith("Built-in"):
            lines.append(f"| {component} | {setting} |")
    lines.append("")

    deployed = state.get("deployed_topics", [])
    if deployed:
        lines.append("### Custom Topics")
        lines.append("")
        lines.append("| # | Topic Name |")
        lines.append("|---|------------|")
        for i, topic in enumerate(deployed, 1):
            lines.append(f"| {i} | `{topic}` |")
        lines.append("")

    # ── Key Findings ──
    lines.append("## Key Findings")
    lines.append("")
    lines.append("### Detector Performance")
    lines.append("")

    # Aggregate detector stats across all iterations
    all_detectors = {}
    for iteration in iterations:
        data = load_iteration_data(iteration)
        det = data.get("vm_logs", {}).get("detector_breakdown", {})
        for name, count in det.items():
            all_detectors[name] = all_detectors.get(name, 0) + count

    if all_detectors:
        lines.append("| Detector | Total Firings (All Iterations) |")
        lines.append("|----------|-------------------------------|")
        for name, count in sorted(all_detectors.items(), key=lambda x: -x[1]):
            lines.append(f"| {name} | {count} |")
        lines.append("")

    lines.append("### Observations")
    lines.append("")
    lines.append("- *[To be filled based on experiment findings]*")
    lines.append("")

    # ── Appendix ──
    lines.append("## Appendix")
    lines.append("")
    lines.append("### A. Topic Deployment Order")
    lines.append("")
    if deployed:
        for i, topic in enumerate(deployed, 1):
            lines.append(f"{i}. `{topic}`")
    else:
        lines.append("*No custom topics deployed yet.*")
    lines.append("")

    lines.append("### B. Data Files")
    lines.append("")
    lines.append("| Iteration | scan_results | parsed_export | vm_logs | gap_report |")
    lines.append("|-----------|-------------|---------------|---------|------------|")
    for iteration in iterations:
        iter_dir = RESULTS_DIR / f"iteration_{iteration:02d}"
        sr = "✓" if (iter_dir / "scan_results.json").exists() else "—"
        pe = "✓" if (iter_dir / "parsed_export.json").exists() else "—"
        vl = "✓" if (iter_dir / "vm_logs.json").exists() else "—"
        gr = "✓" if (iter_dir / "gap_report.md").exists() else "—"
        lines.append(f"| {iteration} | {sr} | {pe} | {vl} | {gr} |")
    lines.append("")

    # Write
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DOCS_DIR / "golden_config_final_report.md"
    out_file.write_text("\n".join(lines) + "\n")
    print(f"\n  Final report saved: {out_file}")
    print(f"  Lines: {len(lines)}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Golden Config — Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Subcommands:
  iteration N   Generate per-iteration report
  log           Rebuild master experiment log from all iterations
  summary       Quick status check (stdout only)
  final         Generate publishable final report
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Report type")

    # iteration
    p_iter = subparsers.add_parser("iteration", help="Generate per-iteration report")
    p_iter.add_argument("iteration_num", type=int, help="Iteration number")

    # log
    subparsers.add_parser("log", help="Rebuild experiment log")

    # summary
    subparsers.add_parser("summary", help="Quick status (stdout)")

    # final
    subparsers.add_parser("final", help="Generate final report")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "iteration":
        cmd_iteration(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "summary":
        cmd_summary(args)
    elif args.command == "final":
        cmd_final(args)


if __name__ == "__main__":
    main()
