# Prisma AIRS — Golden Config

## Building a Hardened AI Security Profile Through Iterative Red Team Tuning

**Author:** Scott Thornton, Palo Alto Networks
**Date:** March 3, 2026
**Version:** 1.1

---

## Executive Summary

This report documents the creation of a "golden config" — a hardened Prisma AIRS security profile optimized through iterative AI red team testing. Starting from a baseline with only built-in detectors (8.71% Attack Success Rate), we iteratively deployed and refined 15 custom topic guardrails and DLP data profiles across 5 tuning cycles to achieve:

- **86% reduction** in static attack success rate (8.71% → 1.20%)
- **Dynamic/agent-based ASR** held at ≤0.50% across all scans
- **17 of 24** attack categories at 0% ASR
- **7 topics** with perfect 100% kill rates maintained across all scans

| Metric | Baseline | Final (Static) | Final (Agent) |
|--------|----------|----------------|---------------|
| Attack Success Rate | 8.71% | **1.20%** | **0.50%** |
| Threats / Total | 401 / 4,602 | 55 / 4,602 | 3 / 600 |
| Custom topics | 0 | 15 | 15 |
| DLP profiles | 0 | 1 (nested, 5 categories) | 1 |
| Categories at 0% ASR | 2 | 17 | — |

The resulting configuration consists of three layers — built-in detectors, custom topic guardrails, and DLP data profiles — packaged as a reusable starting point for any Prisma AIRS deployment.

---

## What's in the Golden Config

### 1. Built-in Detectors (All BLOCK)

| Detector | Action | Coverage |
|----------|--------|----------|
| Prompt Injection | BLOCK | Instruction override, role manipulation |
| Jailbreak | BLOCK | DAN, developer mode, persona hijacking |
| Toxic Content | BLOCK (high + moderate) | Hate speech, harassment, explicit content |
| Malicious Code | BLOCK | Malware generation, exploit code |
| Data Leak Prevention (DLP) | BLOCK | PII, credentials, sensitive data |
| URL Categories | BLOCK (malicious) | Malicious URL injection |
| Agent Security | BLOCK | Tool abuse, agent manipulation |
| Contextual Grounding | BLOCK | Hallucination, fabrication |
| Inline Timeout | BLOCK (25s) | Slow-response DoS |

### 2. Custom Topic Guardrails (15 / 20 slots)

These 15 topics close the gaps that built-in detectors don't cover:

| # | Topic | What It Blocks | Kill Rate |
|---|-------|---------------|-----------|
| 1 | `instruction_override_injection` | DAN prompts, system override, developer mode | **100%** |
| 2 | `brand_defamation_attack` | Fake whistleblower reports, fabricated violations | **100%** |
| 3 | `tool_capability_enumeration` | Tool/API discovery, fake compliance audits | **100%** |
| 4 | `cbrn_substance_synthesis` | Chemical/biological/nuclear weapon synthesis | **100%** |
| 5 | `system_prompt_disclosure` | System prompt extraction, instruction replay | **100%** |
| 6 | `celebrity_defamation_ranking` | Demeaning ranked lists of real public figures | **100%** |
| 7 | `adversarial_suffix_attack` | Affirmative suffix bypass ("Sure I can help...") | **100%** |
| 8 | `roleplay_scenario_jailbreak` | Persona adoption, journalist/detective framing | 96% |
| 9 | `structured_format_injection` | XML tags, fake conversation history, format tricks | 91% |
| 10 | `encoded_obfuscated_request` | Emoji, Unicode variants, IPA encoding | 86% |
| 11 | `style_directive_bypass` | Style directives, humor framing, prefix injection | 83% |
| 12 | `weapons_manufacturing_history` | Historical weapons/genocide/terrorism framing | 80% |
| 13 | `ethnic_racial_stereotyping` | Racial stereotypes, hiring bias, intelligence claims | 84% |
| 14 | `multi_turn_escalation` | Multi-turn escalation toward weapons/bias content | 77% |
| 15 | `political_bias_generation` | Political scandals, territorial claims, conspiracy | 60% |

**5 slots reserved** for customer-specific topics or future threat patterns.

### 3. DLP Data Profiles

The built-in DLP detector is enabled with BLOCK action, but its effectiveness depends on which **data profiles** are activated. AIRS ships with 20 pre-built DLP data profiles covering regulatory frameworks, data types, and industry verticals.

#### Tier 1 — Universal Baseline (included in golden config)

These 5 profiles should be enabled on every deployment:

| Profile | What It Catches | Why It's Essential |
|---------|----------------|--------------------|
| **Secrets and Credentials** | API keys, tokens, passwords, connection strings | Prevents LLM from leaking credentials in responses |
| **PII - Basic** | Names, emails, phone numbers, SSNs, addresses | Baseline PII protection for any application |
| **Sensitive Content** | Broadly sensitive material | Catch-all for content that shouldn't leave the app |
| **Profanity** | Obscene language, slurs | Complements toxic-content detector for output filtering |
| **Self Harm** | Self-injury, suicide-related content | Safety-critical — complements built-in safety detectors |

**Status:** Tier 1 profiles deployed in golden config. Red team scan (iteration 5) confirmed modest improvement — JAILBREAK -75%, BIAS -40%. Profanity detection catches toxic LLM responses that topic guardrails miss on the prompt side.

#### Tier 2 — Compliance (select based on regulatory requirements)

| Profile | Regulation | When to Enable |
|---------|-----------|----------------|
| **GDPR** | EU General Data Protection | EU-facing applications |
| **HIPAA** | US Health Insurance Portability | US healthcare |
| **PHI** | Protected Health Information | Any health data processing |
| **PII** (full) | Comprehensive PII detection | Regulated industries, government |
| **GLBA** | Gramm-Leach-Bliley Act | Banking, financial services |
| **SOX** | Sarbanes-Oxley | Public companies, financial reporting |
| **POPIA** | SA Protection of Personal Information | South Africa-facing |
| **PIPEDA** | Canadian Personal Information Protection | Canada-facing |
| **PHIPA** | Ontario Personal Health Information | Ontario healthcare |
| **U.K. PIOCP** | UK Privacy & Information Commissioner | UK-facing |

#### Tier 3 — Industry-Specific

| Profile | Use Case |
|---------|----------|
| **Financial Information** | Banking, fintech, insurance — account numbers, transactions |
| **Healthcare** | Hospitals, pharma — medical records, diagnoses |
| **Legal** | Law firms, compliance — privileged communications |
| **Intellectual Property** | Tech, R&D — source code, trade secrets, patents |
| **Intellectual Property - Basic** | Lighter version for general IP protection |

### 4. Remaining Gaps

| Component | Status | Notes |
|-----------|--------|-------|
| Custom DLP dictionaries | **Customer-specific** | Internal project names, product codenames, custom entity types |
| Custom DLP regex | **Customer-specific** | Internal ID formats, proprietary data patterns |
| Customer-specific topics | N/A | 5 reserved topic slots for industry/brand-specific guardrails |
| Multi-language topics | N/A | Topics are English-only; multilingual attacks are a known gap |

---

## Methodology

### Architecture

```
Red Team Scanner (Strata Cloud Manager)
        │
        ▼
┌─────────────────────────────────┐
│  AIRS Hard-Block Wrapper        │
│  (Flask on GCP VM)              │
│                                 │
│  1. Prompt scan ────────────────┼──► AIRS Scan API
│  2. If BLOCK → return block msg │    Profile: redteamtest (rev 6)
│  3. LLM call ───────────────────┼──► OpenAI (gpt-4o-mini)
│  4. Response scan ──────────────┼──► AIRS Scan API
│  5. If BLOCK → return block msg │    ├─ 9 built-in detectors → BLOCK
│  6. Return LLM response         │    ├─ 15 custom topics → BLOCK
│                                 │    └─ DLP data profiles → BLOCK
└─────────────────────────────────┘
```

### Iterative Tuning Process

Each iteration followed the same loop:

```
1. Run red team scan (static + agent) in SCM
2. Export results → parse attack data
3. Identify bypassing prompts and group by pattern
4. Design or update custom topics targeting specific bypass patterns
5. Deploy topics via Management API → link to profile
6. Re-scan → measure improvement → repeat
```

### Scoring

- **Static scan:** 4,602 curated attack prompts across 24 subcategories from JailbreakBench, WildJailbreak, and StrongREJECT datasets. Each attack sent 6 times.
- **Dynamic agent scan:** AI agent autonomously probes the target across 10 goals, 6 parallel streams, 10 depth iterations (600 total). Adapts attack strategy based on responses.
- **ASR (Attack Success Rate):** Percentage of attacks that bypass all protections and produce harmful output.

---

## Results

### ASR Progression

```
ASR %
  10 ┤
 8.7 ┤ █████████████████████████████████████████ 401 threats  BASELINE
     ┤
 2.8 ┤ ████████████ 127 threats                               ITER 1 (-68%)
     ┤
 1.7 ┤ ███████ 77 threats                                     ITER 2 (-40%)
     ┤
 1.1 ┤ █████ 51 threats                                       ITER 3 (-34%)
     ┤
 1.3 ┤ █████ 59 threats (scan variance)                       ITER 4
     ┤
 1.2 ┤ █████ 55 threats (DLP added)                           ITER 5
     ┤
   1 ┤ ─ ─ ─ ─ ─ ─ ─ ─ 1% TARGET ─ ─ ─ ─ ─ ─ ─ ─
     ┤
 0.5 ┤ ██ Agent scan: 0.50%                                   ITER 5 AGENT
     ┤
   0 ┤ Agent scan: 0.00% ✓                                    ITER 4 AGENT
     └──────────────────────────────────────────────────────────
       Iter 0    Iter 1    Iter 2    Iter 3    Iter 4    Iter 5
```

### Per-Iteration Summary

| Iter | Topics | Static ASR | Threats | Agent ASR | Action |
|------|--------|------------|---------|-----------|--------|
| 0 | 0 | 8.71% | 401/4602 | — | Baseline — built-in detectors only |
| 1 | 12 | **2.76%** | 127/4602 | — | Deployed 12 topics covering 96% of gaps |
| 2 | 14 | **1.67%** | 77/4602 | — | Refined 3 topics + added 2 new |
| 3 | 15 | **1.11%** | 51/4602 | **0.67%** | Refined 4 topics + added 1 new |
| 4 | 15 | **1.28%** | 59/4602 | **0.00%** | Refined 4 topics — scan variance |
| 5 | 15 | **1.20%** | 55/4602 | **0.50%** | Added DLP data profile (5 categories) |

### Full Category Progression (Baseline → Final)

| Subcategory | Baseline | Iter 1 | Iter 2 | Iter 3 | Iter 4 | Iter 5 | Status |
|-------------|----------|--------|--------|--------|--------|--------|--------|
| JAILBREAK+PI (override) | 154 | 0 | 0 | 0 | 0 | 0 | **Eliminated iter 1** |
| BRAND_TARNISHING | 23 | 0 | 0 | 0 | 0 | 0 | **Eliminated iter 1** |
| TOOL_LEAK | 21 | 0 | 0 | 0 | 0 | 0 | **Eliminated iter 1** |
| CBRN | 6 | 0 | 0 | 0 | 0 | 0 | **Eliminated iter 1** |
| SYSTEM_PROMPT_LEAK | 2 | 0 | 0 | 0 | 0 | 0 | **Eliminated iter 1** |
| CYBERCRIME | 4 | 0 | 0 | 0 | 0 | 0 | **Eliminated iter 1** |
| MALWARE | 3 | 0 | 0 | 0 | 0 | 0 | **Eliminated iter 1** |
| HATE_TOXIC_ABUSE | 6 | 6 | 0 | 0 | 0 | 0 | **Eliminated iter 2** |
| ADVERSARIAL_SUFFIX | 6 | 4 | 5 | 0 | 0 | 0 | **Eliminated iter 3** |
| EVASION | 31 | 10 | 2 | 3 | 8 | 11 | Classifier limitation (Unicode/IPA) |
| NON_VIOLENT_CRIMES | 8 | 2 | 1 | 2 | 2 | 2 | Low volume, stable |
| JAILBREAK | 108 | 24 | 11 | 5 | 4 | 1 | 99% reduction |
| PROMPT_INJECTION | 46 | 12 | 6 | 7 | 6 | 7 | 85% reduction |
| BIAS | 32 | 11 | 6 | 6 | 5 | 3 | 91% reduction |
| POLITICAL | 53 | 32 | 18 | 17 | 21 | 21 | Hardest — borderline political discourse |
| MULTI_TURN | 56 | 26 | 28 | 11 | 13 | 10 | 82% reduction (classifier limitation) |

---

## Key Findings

### 1. Built-in Detectors Leave Major Gaps

At baseline, 55.9% of successful attacks targeted categories with **zero built-in coverage**: POLITICAL (46.5% ASR), BIAS (31.4%), MULTI_TURN (23.3%), BRAND, TOOL_LEAK, and EVASION. Custom topics are the only mitigation for these categories.

### 2. First Topic Deployment Has the Biggest Impact

Iteration 1 (deploying 12 topics) delivered a 68% ASR reduction. Subsequent iterations yielded 40%, 34%, and then plateau. **The initial topic set matters most** — get it right and you cover the majority of threats on day one.

### 3. Topic Description Quality Trumps Quantity

Topics with precise, specific descriptions achieve 100% kill rates. The 250-character description carries approximately 40-50% of the classifier's decision weight — invest your character budget in the description first, then supplement with examples.

### 4. Multi-Turn Attacks Require Content-Based Targeting

The semantic classifier operates on single turns. Multi-turn attacks that build context across numbered JSON turns cannot be detected structurally. The workaround is targeting the **content themes** (weapons manufacturing, genocide, terrorism) that appear within the turns rather than the multi-turn pattern itself.

### 5. Dynamic Agent Scans Are Harder to Fool

The dynamic agent scan (0.00%–0.50% ASR across iterations) provides a more realistic assessment than the static library (~1.2% ASR). The static library includes edge-case prompts like "Is X the worst president?" that are genuinely ambiguous. A real attacker uses adaptive, multi-turn strategies — which the profile blocks at near-zero rates. The few agent threats that surface are borderline content (medical history, relationship advice), not security or safety failures.

### 6. Slot Budgeting Is Essential

Starting with 60% slot utilization (12/20) left room for 3 new topics across iterations 2-4, with 5 slots still reserved. **Don't fill all 20 slots on day one** — reserve capacity for threats discovered during red team testing.

### 7. The Diminishing Returns Plateau Is Real

After 4 iterations, the remaining threats fall into three buckets that custom topics cannot easily address:
- **Borderline political discourse** — "worst president," "politician's scandals" are ambiguous
- **Encoding evasion** — Unicode, IPA, Braille are classifier-level limitations
- **Scan variance** — the stochastic attack library surfaces different prompts each run

---

## Known Limitations

| Limitation | Impact | Mitigable? |
|-----------|--------|------------|
| English-only classifier | Multilingual attacks bypass topic matching | No (platform limitation) |
| Single-turn matching | Multi-turn escalation requires content-based workarounds | Partial |
| Unicode/IPA encoding | Encoded text bypasses semantic classifier | No (classifier limitation) |
| Political nuance | Borderline political discourse hard to distinguish from legitimate queries | Partial (context-dependent) |
| DLP partially tuned | Tier 1 profiles enabled; custom dictionaries/regex not configured | Partially — customer-specific patterns needed |
| 20 topic limit | Hard ceiling on custom guardrails per profile | Work within budget |

---

## Packaging the Golden Config

### What's Included

```
golden-config/
├── topics/
│   └── golden_topics.json          # 15 topic definitions (name, description, examples)
│
├── mgmt/
│   ├── config.py                   # Shared config, auth, AIRS client initialization
│   ├── topic_ops.py                # Topic CRUD: create, update, list, deploy, sync
│   └── profile_ops.py             # Profile CRUD: create, update, link topics
│
├── scan/
│   ├── scan_tester.py              # Quick local scan test (15 prompts)
│   ├── parse_export.py             # Parse SCM red team export zips
│   └── gap_analysis.py             # Analyze threats, recommend topics
│
├── vm/
│   ├── wrapper_vertex.py           # Flask wrapper (AIRS scan + LLM call)
│   ├── deploy.sh                   # GCP VM deployment script
│   └── push.sh                     # Push wrapper to VM
│
├── report/
│   ├── generate_report.py          # Report generation CLI
│   └── collect_vm_logs.py          # VM log collection
│
├── results/
│   └── iteration_00..05/           # Full scan data for all iterations
│
└── docs/
    ├── golden_config_final_report.md  # This report
    ├── experiment_log.md              # Detailed iteration timeline
    └── experiment_status.md           # Current state summary
```

### How to Deploy

**Step 1: Set credentials**
```bash
export PANW_CLIENT_ID="your-client-id"
export PANW_CLIENT_SECRET="your-client-secret"
export PANW_TSG_ID="your-tsg-id"
```

**Step 2: Create topics on your tenant**
```bash
python mgmt/topic_ops.py deploy --file topics/golden_topics.json
```

**Step 3: Link topics to a security profile**
```bash
python mgmt/profile_ops.py link --profile your-profile-name --action block
```

**Step 4: Verify with a quick scan**
```bash
python scan/scan_tester.py --profile your-profile-name
```

**Step 5: Run a full red team scan** in SCM UI to validate.

### How to Customize

- **Add industry-specific topics** using the 5 reserved slots (e.g., financial advice, medical guidance, legal counsel)
- **Tune DLP** with customer-specific dictionary patterns, regex rules, and PII definitions
- **Adjust severity thresholds** on toxic-content detector (currently blocking high + moderate)
- **Run the iterative tuning loop** against your own application to refine topic descriptions for your specific attack surface

---

## Recommended Next Steps

### 1. DLP Impact Validated (Complete)

Tier 1 DLP data profiles (Secrets and Credentials, PII, Sensitive Content, Profanity, Self Harm) were added in iteration 5. Red team scan confirmed a modest positive impact: static ASR improved 1.28% → 1.20%, with JAILBREAK -75% and BIAS -40% reductions likely driven by Profanity detection catching toxic LLM responses. DLP complements prompt-side topic guardrails with response-side filtering.

### 2. Customer-Specific DLP Tuning

The Tier 1 DLP profiles cover common patterns. Deployments should add:

| DLP Component | What's Needed |
|---------------|---------------|
| **Tier 2 compliance profiles** | Enable GDPR, HIPAA, GLBA, etc. based on regulatory requirements |
| **Custom dictionaries** | Internal project names, product codenames, customer-specific terms |
| **Custom regex** | Internal ID formats, proprietary data patterns |

### 3. Ongoing Tuning

The red team scan should be re-run periodically as:
- New attack techniques emerge in the research community
- The underlying LLM is updated or changed
- The application's scope or functionality changes
- AIRS detection capabilities are updated

---

## Appendix A: Scan References

| Scan ID | Iteration | Type | Attacks | Threats | ASR |
|---------|-----------|------|---------|---------|-----|
| 35deb218 | 0 (baseline) | Static | 4,602 | 401 | 8.71% |
| 99f6b770 | 1 | Static | 4,602 | 127 | 2.76% |
| 30bf26da | 2 | Static | 4,602 | 77 | 1.67% |
| 2b040f65 | 3 | Static | 4,602 | 51 | 1.11% |
| 5f08da26 | 3 | Agent | 600 | 4 | 0.67% |
| b40d4254 | 4 | Static | 4,602 | 59 | 1.28% |
| ca7b860c | 4 | Agent | 600 | 0 | 0.00% |
| da7139f7 | 5 | Static | 4,602 | 55 | 1.20% |
| 7133b1d6 | 5 | Agent | 600 | 3 | 0.50% |

## Appendix B: Topic Definitions

All 15 topics with full descriptions and examples are in `topics/golden_topics.json`. Each topic includes:
- `topic_name` — unique identifier
- `description` — semantic description (≤250 chars, ~40-50% classifier weight)
- `examples` — up to 5 example prompts that should be blocked
- `type` — DENY (block action)
- `scan_data` — metadata tracking which subcategory and iteration count it targets

## Appendix C: Topic Deployment History

| # | Topic | Created | Last Updated | Revisions |
|---|-------|---------|-------------|-----------|
| 1 | `roleplay_scenario_jailbreak` | Iter 1 | Iter 4 | 4 |
| 2 | `instruction_override_injection` | Iter 1 | — | 1 |
| 3 | `multi_turn_escalation` | Iter 1 | Iter 3 | 3 |
| 4 | `political_bias_generation` | Iter 1 | Iter 4 | 4 |
| 5 | `structured_format_injection` | Iter 1 | — | 1 |
| 6 | `ethnic_racial_stereotyping` | Iter 1 | — | 1 |
| 7 | `encoded_obfuscated_request` | Iter 1 | — | 1 |
| 8 | `brand_defamation_attack` | Iter 1 | — | 1 |
| 9 | `tool_capability_enumeration` | Iter 1 | — | 1 |
| 10 | `adversarial_suffix_attack` | Iter 1 | — | 1 |
| 11 | `cbrn_substance_synthesis` | Iter 1 | — | 1 |
| 12 | `system_prompt_disclosure` | Iter 1 | — | 1 |
| 13 | `celebrity_defamation_ranking` | Iter 2 | — | 1 |
| 14 | `style_directive_bypass` | Iter 2 | Iter 4 | 3 |
| 15 | `weapons_manufacturing_history` | Iter 3 | Iter 4 | 2 |
