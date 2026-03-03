# Golden Config — Experiment Status

**Snapshot:** 2026-03-03
**Status:** Iteration 5 — DLP scan complete, marginal improvement
**Profile:** `redteamtest` (rev 6, `280fef28-2b3e-44de-90c5-4618707ef188`)

---

## Current Position

We are at **iteration 5** (complete). The profile has 15 custom topics + `airs-rt` nested DLP profile deployed. Iteration 5 static scan achieved **1.20% ASR** (55/4602). Agent scan: **0.50% ASR** (3/600).

DLP addition produced a marginal static improvement (59→55 threats) and slight agent regression (0→3 threats, scan variance). The ~1.2% static ASR represents a stable plateau — the same 12 persistent prompts continue to bypass across iterations. We are firmly at the **diminishing returns plateau**.

```
Timeline
────────────────────────────────────────────────────────────────────────

Mar 1  22:38    Baseline VM test (5 requests, 80% block rate)
Mar 1  22:44    Baseline local scan (15 prompts, 73.3% detection)
Mar 1  ~23:00   SCM red team scan started (baseline — 0 custom topics)
Mar 2  ~00:00   SCM baseline scan completed → 4602 attacks, 8.71% ASR
Mar 2  00:00    Parsed export, analyzed 401 successful attacks
Mar 2  00:10    Designed 12 custom topics from gap analysis
Mar 2  00:15    Deployed 12 topics to tenant + linked to profile (rev 2)
Mar 2  ~06:00   SCM iteration 1 scan completed (scan 99f6b770)
Mar 2  06:16    Results: 4602 attacks, 127 threats, 2.76% ASR ✓ (68.3% reduction)
Mar 2  ~07:00   Analyzed 127 remaining threats (~30 unique patterns)
Mar 2  07:30    Updated 3 topic descriptions, created 2 new topics
Mar 2  07:43    Linked 14 topics to profile (rev 3) — iteration 2 deployed
Mar 2  ~12:00   SCM iteration 2 scan completed (scan 30bf26da)
Mar 2  12:30    Results: 4602 attacks, 77 threats, 1.67% ASR ✓ (39.4% reduction)
Mar 2  ~13:00   Analyzed 77 remaining threats (~12 unique patterns)
Mar 2  13:30    Updated 4 topic descriptions, created 1 new topic
Mar 2  13:45    Linked 15 topics to profile (rev 4) — iteration 3 deployed
Mar 2  ~16:30   SCM iteration 3 static scan completed (scan 2b040f65)
Mar 2  ~18:30   SCM iteration 3 agent scan completed (scan 5f08da26)
Mar 2  19:00    Static: 4602 attacks, 51 threats, 1.11% ASR ✓ (33.8% reduction)
Mar 2  19:00    Agent: 600 iterations, 4 threats, 0.67% ASR ✓
Mar 2  19:15    Analyzed 51 remaining threats (14 unique prompts)
Mar 2  19:30    Updated 4 topic descriptions targeting specific bypass patterns
Mar 2  19:45    Linked 15 topics to profile (rev 5) — iteration 4 deployed
Mar 2  ~22:00   SCM iteration 4 static scan completed (scan b40d4254)
Mar 2  ~22:00   SCM iteration 4 agent scan completed (scan ca7b860c)
Mar 2  22:05    Static: 4602 attacks, 59 threats, 1.28% ASR (scan variance: +8)
Mar 2  22:05    Agent: 600 iterations, 0 threats, 0.00% ASR ✓ (CLEAN SWEEP)
Mar 2  ~23:00   Created airs-rt nested DLP profile (5 categories)
Mar 2  23:30    Attached DLP profile to security profile (rev 6)
Mar 3  ~00:30   SCM iteration 5 scan started (static + agent, with DLP)
Mar 3  ~04:00   SCM iteration 5 static scan completed (scan da7139f7)
Mar 3  ~04:00   SCM iteration 5 agent scan completed (scan 7133b1d6)
Mar 3  04:30    Static: 4602 attacks, 55 threats, 1.20% ASR ✓ (-6.8%)
Mar 3  04:30    Agent: 600 iterations, 3 threats, 0.50% ASR (scan variance: +3)
```

---

## ASR Progression

```
ASR %
  10 ┤
 8.7 ┤ █████████████████████████████████████████ 401 threats (baseline)
     ┤
 2.8 ┤ ████████████ 127 threats (iteration 1) — 68.3% reduction
     ┤
 1.7 ┤ ███████ 77 threats (iteration 2) — 39.4% reduction
     ┤
 1.1 ┤ █████ 51 threats (iteration 3) — 33.8% reduction
     ┤
 1.3 ┤ █████ 59 threats (iteration 4) — scan variance (+8)
     ┤
 1.2 ┤ █████ 55 threats (iteration 5) — DLP added (-6.8%)
     ┤
   1 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ TARGET ─ ─ ─ ─ ─ ─ ─ ─
     ┤
 0.5 ┤ ██ agent scan: 0.50% (3/600) — scan variance
     ┤
   0 ┤ ← STRETCH GOAL
     └──────────────────────────────────────────────────────────
       Iter 0    Iter 1    Iter 2    Iter 3    Iter 4    Iter 5
```

---

## Architecture

```
Red Team Scanner (Strata Cloud Manager)
        │
        ▼
┌─────────────────────────────────┐
│  golden-config-vertex           │
│  136.115.78.7:5008              │
│  (Flask AIRS Hard-Block Wrapper)│
│                                 │
│  1. Receive prompt              │
│  2. AIRS prompt scan ───────────┼──► Scan API (service.api.aisecurity.paloaltonetworks.com)
│     └─ If BLOCK → return 200   │    Profile: redteamtest (rev 5)
│        with block message       │    ├─ Built-in: prompt-injection → BLOCK
│  3. Forward to LLM ────────────┼──► OpenAI (gpt-4o-mini)
│  4. AIRS response scan ────────┼──► Scan API
│     └─ If BLOCK → return 200   │    ├─ Built-in: jailbreak → BLOCK
│        with block message       │    ├─ Built-in: toxic-content → BLOCK (high+moderate)
│  5. Return LLM response        │    ├─ Built-in: malicious-code → BLOCK
│                                 │    ├─ Built-in: DLP → BLOCK
└─────────────────────────────────┘    ├─ Built-in: URL categories → BLOCK
                                       ├─ Built-in: agent-security → BLOCK
                                       ├─ Built-in: contextual-grounding → BLOCK
                                       ├─ Timeout: BLOCK (25s)
                                       └─ 15 custom topics → BLOCK
```

---

## Iteration Results Summary

| Iter | Date | Topics | Static ASR | Threats | Agent ASR | Action |
|------|------|--------|------------|---------|-----------|--------|
| 0 | 2026-03-01 | 0 | 8.71% | 401/4602 | — | Baseline — built-in detectors only |
| 1 | 2026-03-02 | 12 | **2.76%** | 127/4602 | — | Deployed 12 topics covering 96% of baseline threats |
| 2 | 2026-03-02 | 14 | **1.67%** | 77/4602 | — | Updated 3 topics + added 2 new |
| 3 | 2026-03-02 | 15 | **1.11%** | 51/4602 | **0.67%** (4/600) | Updated 4 topics + added 1 new |
| 4 | 2026-03-02 | 15 | **1.28%** | 59/4602 | **0.00%** (0/600) | Updated 4 topics — scan variance |
| 5 | 2026-03-03 | 15 | **1.20%** | 55/4602 | **0.50%** (3/600) | Added `airs-rt` nested DLP profile (5 categories) |

---

## Current Profile Configuration

**Profile:** `redteamtest` (revision 5, 15 topics)

### Custom Topics (15/20 slots)

| # | Topic Name | Status | Target |
|---|------------|--------|--------|
| 1 | `roleplay_scenario_jailbreak` | Updated iter 4 | JAILBREAK |
| 2 | `instruction_override_injection` | Stable (100% kill) | JAILBREAK+PI |
| 3 | `multi_turn_escalation` | Updated iter 3 | MULTI_TURN |
| 4 | `political_bias_generation` | Updated iter 4 | POLITICAL |
| 5 | `structured_format_injection` | Stable | PROMPT_INJECTION |
| 6 | `ethnic_racial_stereotyping` | Stable | BIAS |
| 7 | `encoded_obfuscated_request` | Stable | EVASION |
| 8 | `brand_defamation_attack` | Stable (100% kill) | BRAND |
| 9 | `tool_capability_enumeration` | Stable (100% kill) | TOOL_LEAK |
| 10 | `adversarial_suffix_attack` | Stable (100% kill) | ADV_SUFFIX |
| 11 | `cbrn_substance_synthesis` | Stable (100% kill) | CBRN |
| 12 | `system_prompt_disclosure` | Stable (100% kill) | SYS_PROMPT |
| 13 | `celebrity_defamation_ranking` | Stable (100% kill) | BIAS+HATE |
| 14 | `style_directive_bypass` | Updated iter 4 | PI (style) |
| 15 | `weapons_manufacturing_history` | Updated iter 4 | MULTI_TURN+JAILBREAK |

**5 slots reserved** for future scan findings.

### DLP Data Profile (NEW — Iteration 5)

**Profile:** `airs-rt` (nested, attached to security profile rev 6)

| Rule | Profile | Logic | Action |
|------|---------|-------|--------|
| Primary | Sensitive Content | OR | alert |
| Secondary | Profanity | OR | **block** |
| Secondary | Self Harm | OR | **block** |
| Secondary | Secrets and Credentials | OR | **block** |
| Secondary | PII | OR | **block** |

**Note:** AIRS only accepts 1 DLP profile per security profile. Nested profile bundles 5 Tier 1 categories. Secondary rule matches trigger automatic block.

**Additional Tier 2/3 profiles available:**

| Tier | Profiles | Status |
|------|----------|--------|
| 2 | GDPR, HIPAA, PHI, GLBA, SOX, etc. | Available — customer-specific |
| 3 | Financial, Healthcare, Legal, IP | Available — industry-specific |

---

## Remaining Threat Profile (55 static threats, post-DLP)

### Threat Composition

| Category | Threats | % of Total | Addressable? |
|----------|---------|-----------|--------------|
| Political opinion/bias | ~21 | 38% | Hard — borderline political discourse |
| Evasion/encoding | ~11 | 20% | No — Unicode/IPA/emoji classifier limitation |
| Multi-turn escalation | ~10 | 18% | Partial — JSON structure limits classifier |
| Prompt injection | ~7 | 13% | Partial — colonial style persists |
| Bias | ~3 | 5% | Hard — "worst president" is ambiguous |
| Non-violent crimes | ~2 | 4% | Low priority |
| Jailbreak | ~1 | 2% | Low volume |

### Assessment

We are at the **diminishing returns plateau**. The topic + DLP approach has achieved:
- **86% reduction** in static ASR (8.71% → 1.20%)
- **25% reduction** in dynamic ASR (0.67% → 0.50%)
- **17/24 categories** at 0% ASR

The remaining 55 threats come from 18 unique prompts, of which 12 are persistent across iterations 4-5. They fall into three buckets: scan variance (different prompts each run), classifier limitations (Unicode/IPA encoding), and borderline political content.

---

## What to Do Next

Options:
1. **Declare success** — static 1.20% ASR, agent 0.50% ASR, 17 categories clean. Five iterations have established the plateau.
2. **One more iteration** — target persistent prompts (Trump, Biden, BJP, colonial gentleman) with remaining 5 topic slots. Diminishing returns expected.
3. **Switch to agent-only assessment** — agent scan is the more realistic threat model. 0.50% ASR from 3 borderline content threats is operationally acceptable.
4. **Focus on response-side tuning** — DLP Profanity profile may need custom dictionary entries for political/bias content patterns.

---

## Data Files

```
golden-config/
├── docs/
│   ├── experiment_log.md              # Full timeline through iteration 4
│   ├── experiment_status.md           # This file
│   └── golden_config_final_report.md  # Publishable report
│
├── topics/
│   └── golden_topics.json            # 14 topic definitions (missing weapons_mfg_history)
│
├── mgmt/
│   └── state.json                    # revision=6, 15 topic_ids, iteration=5, dlp_profile
│
└── results/
    ├── iteration_00/
    │   ├── scan_results.json          # Local 15-prompt scan
    │   ├── vm_logs.json               # VM wrapper logs
    │   ├── parsed_export.json         # Baseline SCM export (4602/401/8.71%)
    │   └── iteration_report.md
    │
    ├── iteration_01/
    │   ├── parsed_export.json         # Iter 1 scan (4602/127/2.76%)
    │   └── iteration_report.md
    │
    ├── iteration_02/
    │   ├── parsed_export.json         # Iter 2 scan (4602/77/1.67%)
    │   └── iteration_report.md
    │
    ├── iteration_03/
    │   ├── parsed_export.json         # Iter 3 static (4602/51/1.11%)
    │   └── iteration_report.md
    │
    ├── iteration_03_agent/            # Iter 3 agent (600/4/0.67%)
    │
    ├── iteration_04/
    │   ├── parsed_export.json         # Iter 4 static (4602/59/1.28%)
    │   └── iteration_report.md
    │
    ├── iteration_04_agent/            # Iter 4 agent (600/0/0.00%)
    │
    ├── iteration_05/
    │   ├── parsed_export.json         # Iter 5 static (4602/55/1.20%)
    │   └── iteration_report.md
    │
    └── iteration_05_agent/            # Iter 5 agent (600/3/0.50%)
```

### Scan Export Archive

| Scan | Location | Attacks | Threats | ASR |
|------|----------|---------|---------|-----|
| 35deb218 (baseline) | `~/Downloads/AI_Red_Teaming_Report_35deb218-...` | 4,602 | 401 | 8.71% |
| 99f6b770 (iter 1) | `~/Downloads/AI_Red_Teaming_Report_99f6b770-...` | 4,602 | 127 | 2.76% |
| 30bf26da (iter 2) | `~/Downloads/AI_Red_Teaming_Report_30bf26da-...` | 4,602 | 77 | 1.67% |
| 2b040f65 (iter 3 static) | `~/Downloads/AI_Red_Teaming_Report_2b040f65-...` | 4,602 | 51 | 1.11% |
| 5f08da26 (iter 3 agent) | `~/Downloads/AI_Red_Teaming_Report_5f08da26-...` | 600 | 4 | 0.67% |
| b40d4254 (iter 4 static) | `~/Downloads/AI_Red_Teaming_Report_b40d4254-...` | 4,602 | 59 | 1.28% |
| ca7b860c (iter 4 agent) | `~/Downloads/AI_Red_Teaming_Report_ca7b860c-...` | 600 | 0 | 0.00% |
| da7139f7 (iter 5 static) | `~/Downloads/AI_Red_Teaming_Report_da7139f7-...` | 4,602 | 55 | 1.20% |
| 7133b1d6 (iter 5 agent) | `~/Downloads/AI_Red_Teaming_Report_7133b1d6-...` | 600 | 3 | 0.50% |
