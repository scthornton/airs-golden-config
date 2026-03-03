# AIRS Golden Config

A hardened Prisma AIRS security profile built through iterative red team tuning. Started at 8.71% attack success rate with only built-in detectors — tuned it down to 1.15% static / 0.67% agent across 6 iterations.

```
ASR %
 8.7 ┤ █████████████████████████████████████████ 401 threats  BASELINE
 2.8 ┤ ████████████ 127 threats                               ITER 1 (-68%)
 1.7 ┤ ███████ 77 threats                                     ITER 2 (-40%)
 1.1 ┤ █████ 51 threats                                       ITER 3 (-34%)
 1.3 ┤ █████ 59 threats (scan variance)                       ITER 4
 1.2 ┤ █████ 55 threats (DLP added)                           ITER 5
 1.2 ┤ █████ 53 threats (dual-scan + multi-turn)              ITER 6
     └──────────────────────────────────────────────────────────
       Iter 0  Iter 1  Iter 2  Iter 3  Iter 4  Iter 5  Iter 6
```

## What's In It

**Three layers of protection, all set to BLOCK:**

1. **Built-in detectors** (9) — prompt injection, jailbreak, toxic content, malicious code, DLP, URL categories, agent security, contextual grounding, inline timeout
2. **Custom topic guardrails** (15/20 slots) — semantic classifiers targeting attack categories that built-in detectors miss: political bias, multi-turn escalation, brand defamation, CBRN, system prompt leaks, etc.
3. **DLP data profiles** — nested profile with Tier 1 categories (PII, credentials, profanity, self-harm, sensitive content)

Seven topics hit 100% kill rate and held it across all scans. Five slots are reserved for customer-specific patterns.

## Architecture

```
SCM Red Team Scanner
       │
       ▼
┌────────────────────────┐
│  AIRS Hard-Block       │
│  Wrapper (Flask)       │
│                        │
│  1. Prompt scan ───────┼──► AIRS Scan API
│     (all user turns)   │    Profile: redteamtest
│  2. If BLOCK → stop    │
│  3. LLM call ──────────┼──► OpenAI (gpt-4o-mini)
│  4. Response scan ─────┼──► AIRS (prompt+response)
│  5. Response solo scan ┼──► AIRS (response only)
│  6. If BLOCK → stop    │    ├─ 9 built-in detectors
│  7. Return response    │    ├─ 15 custom topics
│                        │    └─ DLP data profiles
└────────────────────────┘
```

## Quick Start

```bash
# 1. Set credentials
cp .env.example .env   # Fill in your AIRS + OpenAI keys
source .env

# 2. Install SDK
pip install -r requirements.txt
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    pan-airs-api-mgmt-sdk==0.0.1a12

# 3. Initialize state
cp mgmt/state.example.json mgmt/state.json

# 4. Deploy topics to your tenant
python mgmt/topic_ops.py deploy --file topics/golden_topics.json

# 5. Create and configure the security profile
python mgmt/profile_ops.py create

# 6. Verify with a quick scan
python scan/scan_tester.py --limit 5
```

## Repo Structure

```
mgmt/               Management API operations
  config.py          Shared config, auth, AIRS client
  topic_ops.py       Topic CRUD — deploy, update, sync
  profile_ops.py     Security profile CRUD
  dlp_ops.py         DLP data profile operations

scan/               Scan and analysis tools
  scan_tester.py     Quick scan against AIRS API
  parse_export.py    Parse SCM red team exports
  gap_analysis.py    Identify coverage gaps

vm/                 Wrapper deployment
  wrapper_vertex.py  Flask wrapper (AIRS scan + LLM)
  deploy.sh          GCP VM provisioning
  push.sh            Hot-reload wrapper on VM

report/             Reporting
  generate_report.py Per-iteration + final reports
  collect_vm_logs.py VM log collection + parsing

topics/             Topic definitions
  golden_topics.json 15 semantic guardrail topics

results/            Scan data per iteration
docs/               Experiment reports
```

## Iteration Loop

Each tuning cycle:

1. Run red team scan in SCM (static + agent)
2. Export results → `python scan/parse_export.py results/export.zip --iteration N`
3. Analyze gaps → `python scan/gap_analysis.py results/iteration_N/`
4. Deploy/update topics → `python mgmt/topic_ops.py deploy`
5. Generate report → `python report/generate_report.py iteration N`
6. Re-scan. Repeat until satisfied.

## Results

| Iter | Topics | Static ASR | Threats | Agent ASR | What Changed |
|------|--------|------------|---------|-----------|--------------|
| 0 | 0 | 8.71% | 401/4602 | — | Baseline |
| 1 | 12 | **2.76%** | 127/4602 | — | Deployed 12 topics |
| 2 | 14 | **1.67%** | 77/4602 | — | Refined 3, added 2 |
| 3 | 15 | **1.11%** | 51/4602 | **0.67%** | Refined 4, added 1 |
| 4 | 15 | **1.28%** | 59/4602 | **0.00%** | Refined 4 (scan variance) |
| 5 | 15 | **1.20%** | 55/4602 | **0.50%** | Added DLP data profile |
| 6 | 15 | **1.15%** | 53/4602 | **0.67%** | Multi-turn context + dual-scan response |

17 of 24 attack categories reached 0% ASR. The remaining ~1.15% on static scans is borderline political discourse (17.5% sub-ASR), Unicode encoding tricks, and stochastic scan variance — documented in the [full report](docs/golden_config_final_report.md).

## Key Findings

- **Built-in detectors leave major gaps.** 56% of baseline threats targeted categories with zero built-in coverage.
- **First topic deployment is the biggest lever.** Iteration 1 cut ASR by 68%. Each subsequent iteration yielded diminishing returns.
- **Topic description quality > quantity.** Precise descriptions get 100% kill rates. The 250-char description carries ~40-50% of classifier weight.
- **Multi-turn attacks need content targeting.** The classifier matches single turns — target the themes (weapons, genocide, terrorism), not the multi-turn structure.
- **Reserve topic slots.** Starting at 60% utilization left room to adapt. Don't fill all 20 on day one.
- **Dual-scan responses.** Scanning responses both with and without prompt context catches harmful content hidden behind creative prompt framing (word substitution, sci-fi scenarios, emergency framing).
- **Topics have a false-positive floor.** Topics targeting semantically ambiguous domains (system admin, science fiction) block benign content. Accept the gap or find alternative coverage.

## Requirements

- Python 3.10+
- Prisma AIRS tenant with API access (Management + Scan APIs)
- `pan-airs-api-mgmt-sdk` (TestPyPI)
- OpenAI API key (for the wrapper VM)
- GCP project (for VM deployment, optional)

## License

Internal research tooling. See [full report](docs/golden_config_final_report.md) for methodology and findings.
