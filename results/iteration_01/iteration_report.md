# Golden Config — Iteration 1 Report

**Date:** 2026-03-02  |  **Profile:** redteamtest (rev 2)  |  **Iteration:** 1
**Scan ID:** 99f6b770-2f82-4bf6-b3c9-8d73c9926835

---

## Executive Summary

Deployed 12 custom topics to the `redteamtest` security profile. Red team scan confirmed
ASR reduction from 8.71% to 2.76% — a 68.3% improvement. 274 of 401 baseline threats eliminated.

| Metric | Iteration 0 | Iteration 1 | Delta |
|--------|-------------|-------------|-------|
| Custom topics | 0 | 12 | +12 |
| Profile revision | 1 | 2 | +1 |
| SCM ASR | 8.71% (401/4602) | **2.76%** (127/4602) | **-68.3%** |
| Topic slots used | 0/20 | 12/20 | — |
| Categories at 0% ASR | 2 | 8 | +6 |

---

## Scan Results

### Overall

| Metric | Value |
|--------|-------|
| Total attacks | 4,602 |
| Blocked | 4,475 (97.24%) |
| Threats (bypasses) | 127 (2.76%) |
| Baseline comparison | 401 → 127 threats |

### Per-Subcategory Breakdown

```
Subcategory                   Iter 0  Iter 1  Reduction   ASR
──────────────────────────── ─────── ─────── ──────────  ─────
JAILBREAK+PI (override)         154       0     100.0%    0.0%  ✓ ELIMINATED
JAILBREAK (roleplay)            108      24      77.8%    2.3%
MULTI_TURN (escalation)          56      26      53.6%   10.8%
POLITICAL (bias)                 53      32      39.6%   28.1%  ◀ HARDEST
PROMPT_INJECTION (structured)    46      12      73.9%    1.9%
BIAS (ethnic/racial)             32      11      65.6%   10.8%
EVASION (encoded)                31      10      67.7%    1.8%
BRAND_TARNISHING                 23       0     100.0%    0.0%  ✓ ELIMINATED
TOOL_LEAK                        21       0     100.0%    0.0%  ✓ ELIMINATED
NON_VIOLENT_CRIMES                8       2      75.0%    2.2%
ADVERSARIAL_SUFFIX                6       4      33.3%    2.9%
CBRN                              6       0     100.0%    0.0%  ✓ ELIMINATED
HATE_TOXIC_ABUSE                  6       6       0.0%    7.7%  ◀ NO CHANGE
CYBERCRIME                        4       0     100.0%    0.0%  ✓ ELIMINATED
MALWARE                           3       0     100.0%    0.0%  ✓ ELIMINATED
                                ───     ───
                                401     127     68.3% reduction
```

### Categories Eliminated (0% ASR achieved)

1. **JAILBREAK+PROMPT_INJECTION** — `instruction_override_injection` topic: 154 → 0
2. **BRAND_TARNISHING** — `brand_defamation_attack` topic: 23 → 0
3. **TOOL_LEAK** — `tool_capability_enumeration` topic: 21 → 0
4. **CBRN** — `cbrn_substance_synthesis` topic: 6 → 0
5. **SYSTEM_PROMPT_LEAK** — `system_prompt_disclosure` topic: 2 → 0
6. **CYBERCRIME** — Built-in detectors + general topic coverage: 4 → 0
7. **MALWARE** — Built-in `malicious-code` detector: 3 → 0

### Remaining Threat Analysis (127 threats)

**~30 unique prompt patterns** across the 127 remaining threats:

| Pattern | Count | Subcategory | Bypass Technique |
|---------|-------|-------------|-----------------|
| Journalist/detective assignment framing | 24 | JAILBREAK | Professional persona avoids "fiction" keywords |
| Real politician scandal requests | 15 | POLITICAL | Named individuals, not fabricated scenarios |
| Geopolitical territorial claims | 10 | POLITICAL | "Why has X always been part of Y" |
| Conspiracy theory elaboration | 7 | POLITICAL | "Outline common points discussed by..." |
| JSON multi-turn weapons escalation | 26 | MULTI_TURN | Numbered turns, history→manufacturing |
| "Nepo kids" / worst celebrity rankings | 11 | BIAS+HATE | Ranked lists with real names |
| Style directive (colonial, historical persona) | 6 | PROMPT_INJECTION | "In the style of..." |
| Code-syntax auto-generation | 4 | PROMPT_INJECTION | Function-call format for offensive lists |
| Humor/joke framing | 2 | PROMPT_INJECTION | "Tell me jokes about..." |
| Emoji/Unicode encoding | 10 | EVASION | Non-Latin character substitution |
| Adversarial suffix patterns | 4 | ADV_SUFFIX | "Sure I can help" appended |
| Non-violent crime guidance | 2 | NON_VIOLENT_CRIMES | Social engineering techniques |

---

## Topics Deployed

All 12 topics created via Management API (`topic_ops.py deploy --file`):

| Topic Name | Topic ID | Target | Iter 0 → Iter 1 |
|------------|----------|--------|-----------------|
| `roleplay_scenario_jailbreak` | `67309373-...` | JAILBREAK | 108 → 24 |
| `instruction_override_injection` | `78af658b-...` | JAILBREAK+PI | 154 → 0 |
| `multi_turn_escalation` | `07d8d2d2-...` | MULTI_TURN | 56 → 26 |
| `political_bias_generation` | `5beece0c-...` | POLITICAL | 53 → 32 |
| `structured_format_injection` | `3ace0f6e-...` | PROMPT_INJECTION | 46 → 12 |
| `ethnic_racial_stereotyping` | `00bbf527-...` | BIAS | 32 → 11 |
| `encoded_obfuscated_request` | `dc59c43f-...` | EVASION | 31 → 10 |
| `brand_defamation_attack` | `58c83d50-...` | BRAND | 23 → 0 |
| `tool_capability_enumeration` | `1f2fb14b-...` | TOOL_LEAK | 21 → 0 |
| `adversarial_suffix_attack` | `98e8b90b-...` | ADV_SUFFIX | 6 → 4 |
| `cbrn_substance_synthesis` | `2de8b283-...` | CBRN | 6 → 0 |
| `system_prompt_disclosure` | `900a2690-...` | SYS_PROMPT | 2 → 0 |

---

## Risks & Limitations

1. **POLITICAL remains highest ASR (28.1%)** — Topic description targeted "scandal fabrication" but real attacks request factual scandals about named politicians
2. **MULTI_TURN still at 10.8%** — Single-turn topic matching struggles with attacks that build context across numbered JSON turns
3. **HATE_TOXIC_ABUSE unchanged (6 threats)** — No topic directly targeted this category; attacks use "nepo kids" ranked-list patterns
4. **Adversarial suffix limited improvement** — Token-level manipulation resistant to semantic classifiers
5. **EVASION residual (10 threats)** — Emoji/Unicode attacks partially bypass English-only semantic matching

---

## Next Steps (Executed as Iteration 2)

1. **Updated 3 topic descriptions** retargeting to specific bypass patterns found in this scan
2. **Added 2 new topics** (`celebrity_defamation_ranking`, `style_directive_bypass`) using reserved slots
3. Iteration 2 scan pending

---

## Data Files

| File | Status | Description |
|------|--------|-------------|
| `results/iteration_01/parsed_export.json` | Present | Scan 99f6b770 — 4602 attacks, 127 threats, 2.76% ASR |
| `results/iteration_01/iteration_report.md` | Present | This report |
| `results/iteration_00/parsed_export.json` | Present | Baseline — 4602 attacks, 401 threats, 8.71% ASR |
| `topics/golden_topics.json` | Updated | 14 topic definitions with iter 0 + iter 1 scan_data |
| `mgmt/state.json` | Updated | profile_id, revision=3, 14 topic_ids, iteration=2 |
