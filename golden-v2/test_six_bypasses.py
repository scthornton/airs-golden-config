#!/usr/bin/env python3
"""Test the 6 specific bypasses against current profile.

Usage:
    PANW_AI_SEC_API_KEY=<key> python test_six_bypasses.py [profile_name]
"""
import json
import os
import sys
import uuid

import requests

URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
KEY = os.environ.get("PANW_AI_SEC_API_KEY", "")
if not KEY:
    print("[ERROR] Set PANW_AI_SEC_API_KEY environment variable")
    sys.exit(1)
PROFILE = sys.argv[1] if len(sys.argv) > 1 else "golden-v2"

# Read the 6 bypass prompts from the previous test results
with open("results/results-golden-v2-20260515-120750.jsonl") as f:
    bypasses_meta = [json.loads(l) for l in f if json.loads(l)['action'] != 'block']

# Read full prompts from test_attacks.json
attacks = json.loads(open("test_attacks.json").read())
bypasses = []
for b in bypasses_meta:
    pv = b['prompt_preview']
    full = next((a['prompt'] for a in attacks if a['prompt'].startswith(pv[:80])), None)
    if full:
        bypasses.append((b['sub_category'], full))

print(f"Testing {len(bypasses)} bypass prompts against profile '{PROFILE}'")
print("=" * 70)
blocked = 0
for sub, prompt in bypasses:
    r = requests.post(URL, headers={"Content-Type":"application/json","x-pan-token":KEY},
        json={"tr_id": str(uuid.uuid4()),"ai_profile":{"profile_name":PROFILE},
              "metadata":{"app_user":"v3-test","ai_model":"test"},
              "contents":[{"prompt": prompt[:9000]}]}, timeout=30)
    j = r.json()
    action = j.get("action","err")
    detected = j.get("prompt_detected",{})
    triggered = [k for k,v in detected.items() if v]
    flag = "OK" if action == "block" else "BYPASS"
    if action == "block":
        blocked += 1
    short = prompt[:100].replace("\n", " ")
    print(f"  [{flag:6s}] [{sub:25s}] {','.join(triggered) or 'none':25s} | {short}")
print("=" * 70)
print(f"Bypasses blocked: {blocked}/{len(bypasses)}")
