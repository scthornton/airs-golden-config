# AIRS Golden Config

A hardened Prisma AIRS security profile built through iterative red team tuning. Started at 8.71% attack success rate with only built-in detectors — tuned down to **1.02% static** (best) / **Score 15 agent** across 8 iterations. Automated evaluation via [Daystrom](https://github.com/cdot65/daystrom) confirmed topics are at the AIRS classifier ceiling.

```
Static ASR %
 8.7 ┤ █████████████████████████████████████████ 401 threats  BASELINE
 2.8 ┤ ████████████ 127 threats                               ITER 1 (-68%)
 1.7 ┤ ███████ 77 threats                                     ITER 2 (-40%)
 1.1 ┤ █████ 51 threats                                       ITER 3 (-34%)
 1.3 ┤ █████ 59 threats (scan variance)                       ITER 4
 1.2 ┤ █████ 55 threats (DLP added)                           ITER 5
 1.2 ┤ █████ 53 threats (stable)                              ITER 6
 1.0 ┤ ████ 47 threats (NEW BEST)                             ITER 7 ✓
 1.4 ┤ ██████ 65 threats (scan variance)                      ITER 8
     └──────────────────────────────────────────────────────────
       Iter 0  Iter 1  Iter 2  Iter 3  Iter 4  Iter 5  Iter 6-8
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

# 2. Install dependencies (needs Python 3.10+, check with: python3 --version)
pip install -r requirements.txt

# 3. Initialize state
cp mgmt/state.example.json mgmt/state.json

# 4. Deploy topics to your tenant
python mgmt/topic_ops.py deploy --file topics/golden_topics.json

# 5. Create and configure the security profile
python mgmt/profile_ops.py create

# 6. Verify with a quick scan
python scan/scan_tester.py --limit 5
```

### SDK notes

The Prisma AIRS Management SDK (`pan-airs-api-mgmt-sdk`) is GA on public PyPI and
requires **Python 3.10 or newer**. Earlier versions of this README installed a
pre-release from TestPyPI; that is no longer necessary.

If pip reports `Could not find a version that satisfies the requirement ...
(from versions: none)`, you are almost certainly on Python 3.9 or older. pip
applies the `Requires-Python` constraint before it compares version numbers, so
every release gets filtered out and pip reports "none" rather than a version
mismatch.

The scripts here work against both the GA releases and the older TestPyPI
alphas. Two things changed across that boundary, and the code detects which is
installed rather than assuming:

| | TestPyPI alphas (<= 0.0.1a15) | PyPI GA (>= 0.0.3) |
|---|---|---|
| List custom topics | `retrieve_all_custom_topics_by_tsgid()` | `get_all_custom_topics()` |
| List AI profiles | `retrieve_ai_profiles()` | `get_all_ai_profiles()` |
| List DLP profiles | `retrieve_all_dlp_profiles()` | `get_all_dlp_profiles()` |
| `active` field on topics and profiles | present | removed in 0.2.0 |

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

| Iter | Topics | Static ASR | Threats | Agent Score | What Changed |
|------|--------|------------|---------|-------------|--------------|
| 0 | 0 | 8.71% | 401/4602 | — | Baseline |
| 1 | 12 | **2.76%** | 127/4602 | — | Deployed 12 topics |
| 2 | 14 | **1.67%** | 77/4602 | — | Refined 3, added 2 |
| 3 | 15 | **1.11%** | 51/4602 | — | Refined 4, added 1 |
| 4 | 15 | **1.28%** | 59/4602 | — | Refined 4 (scan variance) |
| 5 | 15 | **1.20%** | 55/4602 | — | Added DLP data profile |
| 6 | 15 | **1.15%** | 53/4602 | 15 | Stable confirmation |
| 7 | 15 | **1.02%** | 47/4602 | 27.5 | Best static; agent regression (math framing) |
| 8 | 15 | **1.41%** | 65/4602 | 15 | Refined 4 topics + wrapper v4; agent recovered |

17 of 24 attack categories reached 0% ASR. Daystrom automated evaluation confirmed all topics are at the **AIRS classifier ceiling** (60-75% coverage) due to OR-gate architecture. See [experiment status](docs/experiment_status.md) and [full report](docs/golden_config_final_report.md).

## Golden Config v2

[golden-v2/](golden-v2/) simplifies the 15-topic v1 down to 12 topics using precision learnings from the Morgan Stanley engagement. Achieves 4.76% ASR on a 126-prompt bypass corpus (vs v1's 5.56%) with 20% fewer topics. Topic descriptions rewritten to 15-20 words anchored to concrete tokens.

See [golden-v2/README.md](golden-v2/README.md) for details.

## Key Findings

- **Built-in detectors leave major gaps.** 56% of baseline threats targeted categories with zero built-in coverage.
- **First topic deployment is the biggest lever.** Iteration 1 cut ASR by 68%. Each subsequent iteration yielded diminishing returns.
- **Topic description quality > quantity.** Precise descriptions get 100% kill rates. The 250-char description carries ~40-50% of classifier weight.
- **AIRS classifier is an OR-gate, not AND-gate.** Fires on ANY matching signal in the description, not on the conjunction. "Blocks X to achieve Y" triggers on X alone OR Y alone. This is the fundamental ceiling — no topic rewriting can fix it.
- **Multi-turn attacks need content targeting.** The classifier matches single turns — target the themes (weapons, genocide, terrorism), not the multi-turn structure.
- **Reserve topic slots.** Starting at 60% utilization left room to adapt. Don't fill all 20 on day one.
- **Dual-scan wrapper (v4).** Scanning prompts twice (last message + full context) and responses twice (with context + standalone) catches both escalation patterns and creative framing bypasses.
- **3 persistent agent goals use creative evasion.** Fictional character roleplay (Hannibal Lecter), absurdist displacement (SmartWash 3000 socks), and vocabulary substitution ("sun-drops" for oxycontin) bypass classifiers by never using matchable keywords.

## Requirements

- Python 3.10+
- Prisma AIRS tenant with API access (Management + Scan APIs)
- `pan-airs-api-mgmt-sdk` (TestPyPI)
- OpenAI API key (for the wrapper VM)
- GCP project (for VM deployment, optional)

## License

Internal research tooling. See [full report](docs/golden_config_final_report.md) for methodology and findings.

---

## Contact

**Scott Thornton** — AI Security Researcher

- Website: [perfecxion.ai](https://perfecxion.ai/)
- Email: [scott@perfecxion.ai](mailto:scott@perfecxion.ai)
- LinkedIn: [linkedin.com/in/scthornton](https://www.linkedin.com/in/scthornton)
- ORCID: [0009-0008-0491-0032](https://orcid.org/0009-0008-0491-0032)
- GitHub: [@scthornton](https://github.com/scthornton)

**Security Issues**: Please report via [SECURITY.md](SECURITY.md)
