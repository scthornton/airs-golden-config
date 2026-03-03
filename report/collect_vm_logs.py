#!/usr/bin/env python3
"""
Collect and parse VM wrapper logs into structured JSON.

Pulls the Flask service log from the golden-config VM via gcloud SSH,
parses each line into structured events, and aggregates summary stats.

Usage:
    python report/collect_vm_logs.py                              # Pull all logs
    python report/collect_vm_logs.py --since "2026-03-02 03:49"   # Since timestamp
    python report/collect_vm_logs.py --iteration 0                # Save to iteration dir
    python report/collect_vm_logs.py --from-file /tmp/service.log # Parse local file
"""

import sys
import os
import re
import ast
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from collections import Counter

RESULTS_DIR = Path(__file__).parent.parent / "results"

# VM defaults
DEFAULT_VM_NAME = "golden-config-vertex"
DEFAULT_ZONE = "us-central1-a"
LOG_PATH = "~/service.log"

# ── Log line patterns ────────────────────────────────────────────────────────
# Timestamps from Python logging: "2026-03-01 22:38:15,123"
TS_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"

# Pattern 1: AIRS prompt scan result
#   2026-03-01 22:38:15,123 INFO AIRS prompt scan: action=block category=malicious detections={'agent': True, ...}
RE_PROMPT_SCAN = re.compile(
    TS_PATTERN + r" INFO AIRS prompt scan: action=(\w+) category=(\w+) detections=(\{.*\})"
)

# Pattern 2: Blocked prompt
#   2026-03-01 22:38:15,456 INFO BLOCKED prompt: Ignore all previous...
RE_BLOCKED_PROMPT = re.compile(
    TS_PATTERN + r" INFO BLOCKED prompt: (.+)"
)

# Pattern 3: AIRS response scan result
#   2026-03-01 22:38:16,789 INFO AIRS response scan: action=allow category=benign
RE_RESPONSE_SCAN = re.compile(
    TS_PATTERN + r" INFO AIRS response scan: action=(\w+) category=(\w+)"
)

# Pattern 4: Blocked response
#   2026-03-01 22:38:16,999 INFO BLOCKED response for prompt: ...
RE_BLOCKED_RESPONSE = re.compile(
    TS_PATTERN + r" INFO BLOCKED response for prompt: (.+)"
)

# Pattern 5: HTTP request line (Flask/werkzeug)
#   2026-03-01 22:38:15,000 INFO 35.197.73.227 - - [01/Mar/2026 22:38:15] "POST /v1/chat/completions HTTP/1.1" 200 -
RE_REQUEST = re.compile(
    TS_PATTERN + r' INFO (\d+\.\d+\.\d+\.\d+) - - \[.*?\] "(\w+) ([\S]+) HTTP/[\d.]+" (\d+) -'
)

# Pattern 6: AIRS scan error
RE_SCAN_ERROR = re.compile(
    TS_PATTERN + r" ERROR (AIRS (?:scan|response scan) (?:error|HTTP \d+): .+)"
)


def pull_logs(vm_name: str, zone: str, since: str = None) -> str:
    """Pull logs from VM via gcloud SSH."""
    if since:
        # Use grep to filter lines after the timestamp
        cmd = f"cat {LOG_PATH}"
    else:
        cmd = f"cat {LOG_PATH}"

    full_cmd = [
        "gcloud", "compute", "ssh", vm_name,
        f"--zone={zone}",
        f"--command={cmd}",
    ]

    print(f"  Pulling logs from {vm_name} ({zone})...")
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        print(f"[ERROR] gcloud SSH failed: {result.stderr.strip()}")
        sys.exit(1)

    raw = result.stdout
    print(f"  Received {len(raw)} bytes, {raw.count(chr(10))} lines")

    if since:
        # Filter lines with timestamp >= since
        filtered = []
        for line in raw.splitlines():
            ts_match = re.match(TS_PATTERN, line)
            if ts_match:
                line_ts = ts_match.group(1).replace(",", ".")
                if line_ts >= since:
                    filtered.append(line)
            else:
                # Continuation lines (stack traces, etc.) — include if we're past the cutoff
                if filtered:
                    filtered.append(line)
        raw = "\n".join(filtered)
        print(f"  After --since filter: {len(filtered)} lines")

    return raw


def parse_detections(det_str: str) -> dict:
    """Parse Python dict repr from log line (e.g., {'agent': True, 'dlp': False})."""
    try:
        return ast.literal_eval(det_str)
    except (ValueError, SyntaxError):
        return {}


def parse_logs(raw: str) -> dict:
    """Parse raw log text into structured events and summary."""
    events = []
    source_ips = set()
    detector_counts = Counter()

    prompt_scans = 0
    prompt_blocked = 0
    response_scans = 0
    response_blocked = 0
    requests_total = 0
    errors = 0

    first_ts = None
    last_ts = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # Extract timestamp for period tracking
        ts_match = re.match(TS_PATTERN, line)
        if ts_match:
            ts_str = ts_match.group(1)
            if first_ts is None:
                first_ts = ts_str
            last_ts = ts_str

        # Pattern 1: Prompt scan result
        m = RE_PROMPT_SCAN.match(line)
        if m:
            ts, action, category, det_str = m.groups()
            detections = parse_detections(det_str)
            prompt_scans += 1

            # Count detector firings
            for det_name, fired in detections.items():
                if fired:
                    detector_counts[det_name] += 1

            events.append({
                "timestamp": ts,
                "event": "prompt_scan",
                "action": action,
                "category": category,
                "detections": detections,
            })
            continue

        # Pattern 2: Blocked prompt
        m = RE_BLOCKED_PROMPT.match(line)
        if m:
            ts, prompt_preview = m.groups()
            prompt_blocked += 1
            events.append({
                "timestamp": ts,
                "event": "prompt_blocked",
                "prompt_preview": prompt_preview.strip()[:200],
            })
            continue

        # Pattern 3: Response scan
        m = RE_RESPONSE_SCAN.match(line)
        if m:
            ts, action, category = m.groups()
            response_scans += 1
            events.append({
                "timestamp": ts,
                "event": "response_scan",
                "action": action,
                "category": category,
            })
            continue

        # Pattern 4: Blocked response
        m = RE_BLOCKED_RESPONSE.match(line)
        if m:
            ts, prompt_preview = m.groups()
            response_blocked += 1
            events.append({
                "timestamp": ts,
                "event": "response_blocked",
                "prompt_preview": prompt_preview.strip()[:200],
            })
            continue

        # Pattern 5: HTTP request
        m = RE_REQUEST.match(line)
        if m:
            ts, ip, method, path, status = m.groups()
            if path == "/v1/chat/completions":
                requests_total += 1
                source_ips.add(ip)
                events.append({
                    "timestamp": ts,
                    "event": "request",
                    "source_ip": ip,
                    "method": method,
                    "path": path,
                    "status": int(status),
                })
            continue

        # Pattern 6: Errors
        m = RE_SCAN_ERROR.match(line)
        if m:
            ts, error_msg = m.groups()
            errors += 1
            events.append({
                "timestamp": ts,
                "event": "error",
                "message": error_msg[:300],
            })
            continue

    # Calculate allowed_through: prompt scans where action was not "block"
    prompt_allowed = sum(
        1 for e in events
        if e["event"] == "prompt_scan" and e.get("action") != "block"
    )

    # Total blocked = prompt_blocked + response_blocked
    total_blocked = prompt_blocked + response_blocked
    # Denominator for block rate: use prompt_scans (each request gets one prompt scan)
    total_for_rate = prompt_scans if prompt_scans > 0 else 1
    block_rate = round(total_blocked / total_for_rate * 100, 1)

    return {
        "collected_at": datetime.now().isoformat(),
        "vm_name": DEFAULT_VM_NAME,
        "period": {
            "start": first_ts,
            "end": last_ts,
        },
        "summary": {
            "total_requests": requests_total,
            "prompt_scans": prompt_scans,
            "prompt_blocked": prompt_blocked,
            "response_scans": response_scans,
            "response_blocked": response_blocked,
            "allowed_through": prompt_allowed,
            "errors": errors,
            "block_rate_percent": block_rate,
            "unique_source_ips": sorted(source_ips),
        },
        "detector_breakdown": dict(detector_counts.most_common()),
        "timeline": events,
    }


def save_vm_logs(data: dict, iteration: int = None):
    """Save parsed logs to the iteration directory."""
    if iteration is None:
        existing = sorted(RESULTS_DIR.glob("iteration_*"))
        iteration = len(existing) - 1 if existing else 0

    iter_dir = RESULTS_DIR / f"iteration_{iteration:02d}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    out_file = iter_dir / "vm_logs.json"

    # Save full data but limit timeline to keep file manageable
    save_data = {k: v for k, v in data.items() if k != "timeline"}
    # Keep timeline but truncate prompt previews
    save_data["timeline"] = data["timeline"]

    out_file.write_text(json.dumps(save_data, indent=2) + "\n")
    print(f"\n  VM logs saved: {out_file}")
    print(f"  Timeline events: {len(data['timeline'])}")
    return out_file


def print_summary(data: dict):
    """Print human-readable summary."""
    s = data["summary"]
    print(f"\n  {'='*55}")
    print(f"  VM LOG SUMMARY — {data['vm_name']}")
    print(f"  {'='*55}")
    print(f"  Period:           {data['period']['start']} → {data['period']['end']}")
    print(f"  Requests:         {s['total_requests']}")
    print(f"  Prompt scans:     {s['prompt_scans']}")
    print(f"  Prompt blocked:   {s['prompt_blocked']}")
    print(f"  Response scans:   {s['response_scans']}")
    print(f"  Response blocked: {s['response_blocked']}")
    print(f"  Allowed through:  {s['allowed_through']}")
    print(f"  Errors:           {s['errors']}")
    print(f"  Block rate:       {s['block_rate_percent']}%")
    print(f"  Source IPs:       {', '.join(s['unique_source_ips']) or 'none'}")

    det = data.get("detector_breakdown", {})
    if det:
        print(f"\n  Detector breakdown:")
        for name, count in sorted(det.items(), key=lambda x: -x[1]):
            print(f"    {count:>6}  {name}")

    print(f"  {'='*55}")


def main():
    parser = argparse.ArgumentParser(description="Golden Config — Collect VM Logs")
    parser.add_argument("--iteration", type=int, help="Iteration number for output dir")
    parser.add_argument("--since", help='Filter logs since timestamp (e.g., "2026-03-02 03:49")')
    parser.add_argument("--vm", default=DEFAULT_VM_NAME, help=f"VM name (default: {DEFAULT_VM_NAME})")
    parser.add_argument("--zone", default=DEFAULT_ZONE, help=f"GCP zone (default: {DEFAULT_ZONE})")
    parser.add_argument("--from-file", dest="from_file", help="Parse local log file instead of SSH")
    parser.add_argument("--no-save", action="store_true", help="Don't save to disk")
    args = parser.parse_args()

    # Get raw logs
    if args.from_file:
        path = Path(args.from_file)
        if not path.exists():
            print(f"[ERROR] File not found: {args.from_file}")
            sys.exit(1)
        raw = path.read_text()
        print(f"  Reading local file: {args.from_file} ({len(raw)} bytes)")
    else:
        raw = pull_logs(args.vm, args.zone, since=args.since)

    if not raw.strip():
        print("[WARN] No log data received.")
        return

    # Parse
    data = parse_logs(raw)
    data["vm_name"] = args.vm

    # Display
    print_summary(data)

    # Save
    if not args.no_save:
        save_vm_logs(data, iteration=args.iteration)


if __name__ == "__main__":
    main()
