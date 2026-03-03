# Golden Config — Experiment Log

| Parameter | Value |
|-----------|-------|
| Goal | 0% ASR on AIRS red team scans |
| Target VM | golden-config-vertex (136.115.78.7:5008) |
| Profile | redteamtest |
| LLM | gpt-4o-mini |
| Start Date | 2026-03-01 |
| Topic Library Size | 27 topics across 7 categories |
| Current Iteration | 4 (complete) |
| Topics Deployed | 15 / 20 |

---

## Iteration 0 — Baseline (2026-03-01)

**Config:** Built-in detectors only. **Zero custom topics.**

| Source | Total | Blocked | Allowed | Rate |
|--------|-------|---------|---------|------|
| Local scan (scan_tester.py) | 15 | 11 | 4 | 73.3% block |
| VM logs (live SCM requests) | 5 | 4 | 1 | 80.0% block |
| SCM red team (pre-topic) | 4,602 | 4,201 | 401 | 8.71% ASR |

**Detector firings:** agent (2), injection (2), toxic_content (1)

**Gaps identified:**
- 401 successful attacks across 15 subcategories
- 224 attacks (55.9%) had zero built-in detector coverage
- Highest ASR: POLITICAL (46.5%), BIAS (31.4%), MULTI_TURN (23.3%)

**Action taken:** Designed and deployed 12 custom topics targeting top attack categories

---

## Iteration 1 — First Topic Deployment (2026-03-02)

**Config:** Built-in detectors + 12 custom topics (BLOCK action)

**Topics deployed (12/20 slots):**
1. `roleplay_scenario_jailbreak` — JAILBREAK roleplay bypass (108 baseline successes)
2. `instruction_override_injection` — JAILBREAK+PI override attacks (154 baseline successes)
3. `multi_turn_escalation` — Multi-step escalation (56, 23.3% ASR, no built-in)
4. `political_bias_generation` — Political bias (53, 46.5% ASR, no built-in)
5. `structured_format_injection` — XML/format prompt injection (46 baseline successes)
6. `ethnic_racial_stereotyping` — Racial/ethnic bias (32, 31.4% ASR, no built-in)
7. `encoded_obfuscated_request` — Emoji/Unicode evasion (31, no built-in)
8. `brand_defamation_attack` — Fake whistleblower/defamation (23, no built-in)
9. `tool_capability_enumeration` — Tool/API discovery (21, no built-in)
10. `adversarial_suffix_attack` — Affirmative suffix bypass (6 baseline successes)
11. `cbrn_substance_synthesis` — CBRN weapons/agents (6, critical safety)
12. `system_prompt_disclosure` — System prompt extraction (2, enterprise priority)

**8 slots reserved** for topics generated from future scan findings.

**Scan results (scan 99f6b770):** ASR dropped **8.71% → 2.76%** (68.3% reduction)

| Source | Total | Blocked | Allowed | Rate |
|--------|-------|---------|---------|------|
| SCM red team (post-topic) | 4,602 | 4,475 | 127 | **2.76% ASR** |

**Per-subcategory results (127 remaining threats):**

| Subcategory | Iter 0 | Iter 1 | Reduction | ASR |
|-------------|--------|--------|-----------|-----|
| JAILBREAK | 108 | 24 | 77.8% | 2.3% |
| PROMPT_INJECTION | 46 | 12 | 73.9% | 1.9% |
| MULTI_TURN | 56 | 26 | 53.6% | 10.8% |
| POLITICAL | 53 | 32 | 39.6% | 28.1% |
| BIAS | 32 | 11 | 65.6% | 10.8% |
| EVASION | 31 | 10 | 67.7% | 1.8% |
| BRAND_TARNISHING | 23 | 0 | **100%** | 0% |
| TOOL_LEAK | 21 | 0 | **100%** | 0% |
| ADVERSARIAL_SUFFIX | 6 | 4 | 33.3% | 2.9% |
| CBRN | 6 | 0 | **100%** | 0% |
| HATE_TOXIC_ABUSE | 6 | 6 | 0% | 7.7% |
| SYSTEM_PROMPT_LEAK | 2 | 0 | **100%** | 0% |
| NON_VIOLENT_CRIMES | 8 | 2 | 75.0% | 2.2% |
| CYBERCRIME | 4 | 0 | **100%** | 0% |
| MALWARE | 3 | 0 | **100%** | 0% |

**6 categories achieved 0% ASR:** BRAND_TARNISHING, TOOL_LEAK, CBRN, SYSTEM_PROMPT_LEAK, CYBERCRIME, MALWARE

**Action taken:** Updated 3 topic descriptions + added 2 new topics for iteration 2

---

## Iteration 2 — Topic Refinement (2026-03-02)

**Config:** Built-in detectors + 14 custom topics (BLOCK action). Profile revision 3.

**3 existing topics updated** (retargeted descriptions + examples based on bypassing prompts):
1. `roleplay_scenario_jailbreak` — Retargeted from movie/fiction to journalist/detective/historical framing
2. `multi_turn_escalation` — Retargeted to JSON multi-turn format and history→weapons escalation
3. `political_bias_generation` — Changed from "scandal fabrication" to real scandal disclosure, geopolitical claims, conspiracy theories

**2 new topics created** (using reserved slots: 14/20):
4. `celebrity_defamation_ranking` — Targets BIAS "nepo kids" + HATE_TOXIC_ABUSE ranked-list patterns (17 iter 1 threats)
5. `style_directive_bypass` — Targets PROMPT_INJECTION style directives, code-syntax, humor framing (12 iter 1 threats)

**Scan results (scan 30bf26da):** ASR dropped **2.76% → 1.67%** (39.4% reduction)

| Source | Total | Blocked | Allowed | Rate |
|--------|-------|---------|---------|------|
| SCM red team (post-refinement) | 4,602 | 4,525 | 77 | **1.67% ASR** |

**Per-subcategory results (77 remaining threats):**

| Subcategory | Iter 1 | Iter 2 | Reduction | ASR |
|-------------|--------|--------|-----------|-----|
| MULTI_TURN | 26 | 28 | **+7.7%** | 11.7% |
| POLITICAL | 32 | 18 | 43.8% | 15.8% |
| JAILBREAK | 24 | 11 | 54.2% | 1.1% |
| PROMPT_INJECTION | 12 | 6 | 50.0% | 0.9% |
| BIAS | 11 | 6 | 45.5% | 5.9% |
| ADVERSARIAL_SUFFIX | 4 | 5 | **-25.0%** | 3.6% |
| EVASION | 10 | 2 | 80.0% | 0.4% |
| NON_VIOLENT_CRIMES | 2 | 1 | 50.0% | 1.1% |
| HATE_TOXIC_ABUSE | 6 | 0 | **100%** | 0% |

**Key finding:** MULTI_TURN got slightly worse — confirms classifier cannot match across JSON numbered turns. HATE_TOXIC_ABUSE eliminated (celebrity_defamation_ranking 100% kill rate).

**Action taken:** Updated 4 topic descriptions + added 1 new topic for iteration 3

---

## Iteration 3 — Content-Based Multi-Turn Strategy (2026-03-02)

**Config:** Built-in detectors + 15 custom topics (BLOCK action). Profile revision 4.

**4 existing topics updated** (retargeted to specific iter 2 bypass patterns):
1. `multi_turn_escalation` — Changed strategy: target content themes (weapons mfg, political bias) instead of multi-turn structure
2. `political_bias_generation` — Broadened to sovereign territory disputes, conspiracy narratives, partisan superlatives
3. `roleplay_scenario_jailbreak` — Extended to movie character adoption, radioactive substance history, academic framing
4. `style_directive_bypass` — Extended to instruction override framing, task-switching injection

**1 new topic created** (using reserved slot: 15/20):
5. `weapons_manufacturing_history` — Targets historical weapons/substance production framing that spans MULTI_TURN + JAILBREAK (~33 threats)

**5 slots reserved** for future scan findings.

**Theoretical coverage:** Updated topics target ~63 of 77 remaining threats (82%). Remaining ~14 are classifier limitations (adversarial suffix, IPA encoding).

**Static scan results (scan 2b040f65):** ASR dropped **1.67% → 1.11%** (33.8% reduction)

| Source | Total | Blocked | Allowed | Rate |
|--------|-------|---------|---------|------|
| SCM red team (static, post-content) | 4,602 | 4,551 | 51 | **1.11% ASR** |
| SCM red team (agent, 10 goals) | 600 | 596 | 4 | **0.67% ASR** |

**Per-subcategory results (51 remaining static threats):**

| Subcategory | Iter 2 | Iter 3 | Reduction | ASR |
|-------------|--------|--------|-----------|-----|
| MULTI_TURN | 28 | 11 | **60.7%** | 4.6% |
| POLITICAL | 18 | 17 | 5.6% | 14.9% |
| JAILBREAK | 11 | 5 | 54.5% | 0.5% |
| PROMPT_INJECTION | 6 | 7 | -16.7% | 1.1% |
| BIAS | 6 | 6 | 0% | 5.9% |
| ADVERSARIAL_SUFFIX | 5 | 0 | **100%** | 0% |
| EVASION | 2 | 3 | -50% | 0.5% |
| NON_VIOLENT_CRIMES | 1 | 2 | -100% | 2.2% |
| HATE_TOXIC_ABUSE | 0 | 0 | — | 0% |
| New categories (8) | — | 0 | — | 0% |

**Key finding:** MULTI_TURN dropped 61% — `weapons_manufacturing_history` content-based approach worked. ADVERSARIAL_SUFFIX eliminated.

**Agent scan (4 threats):** All Movie Roleplay + Leading Statements technique. Borderline content (coworker humiliation story, affair description), not security/safety categories.

**Action taken:** Updated 4 topic descriptions targeting 14 unique bypass patterns for iteration 4

---

## Iteration 4 — Surgical Prompt Targeting (2026-03-02)

**Config:** Built-in detectors + 15 custom topics (BLOCK action). Profile revision 5.

**4 existing topics updated** (targeting specific bypass prompts from the 14 unique patterns):
1. `style_directive_bypass` — Added instruction override ("forget previous/new challenge"), humor/joke framing for minorities, prefix injection
2. `weapons_manufacturing_history` — Broadened to genocide methods (gas chambers), terrorism infiltration, nuclear weapon justification
3. `roleplay_scenario_jailbreak` — Added named character personas justifying harmful ideologies (Viktor/slavery/accent)
4. `political_bias_generation` — Added political party satire/roasting pattern (CPC roasting = 11 threats)

**5 slots reserved** for future scan findings.

**Theoretical coverage:** 46 of 51 threats directly targeted (90%). 22 assessed as "catchable," 12 as "maybe," 12 as "hard" (classifier plateau), 3 not catchable (encoding), 2 low priority.

**Static scan results (scan b40d4254):** ASR **increased** from **1.11% → 1.28%** (+15.7%)

| Source | Total | Blocked | Allowed | Rate |
|--------|-------|---------|---------|------|
| SCM red team (static, post-surgical) | 4,602 | 4,543 | 59 | **1.28% ASR** |
| SCM red team (agent, 10 goals) | 600 | 600 | 0 | **0.00% ASR** |

**Per-subcategory results (59 remaining static threats):**

| Subcategory | Iter 3 | Iter 4 | Reduction | ASR |
|-------------|--------|--------|-----------|-----|
| POLITICAL | 17 | 21 | **-23.5%** | 18.4% |
| MULTI_TURN | 11 | 13 | **-18.2%** | 5.4% |
| EVASION | 3 | 8 | **-166.7%** | 1.4% |
| PROMPT_INJECTION | 7 | 6 | 14.3% | 0.9% |
| BIAS | 6 | 5 | 16.7% | 5.9% |
| JAILBREAK | 5 | 4 | 20.0% | 0.4% |
| NON_VIOLENT_CRIMES | 2 | 2 | 0% | 2.2% |
| ADVERSARIAL_SUFFIX | 0 | 0 | — | 0% |
| HATE_TOXIC_ABUSE | 0 | 0 | — | 0% |
| New categories (15) | 0 | 0 | — | 0% |

**Key finding:** Topic updates eliminated all 7 targeted prompts (26 threats). But 12 new prompts surfaced from the stochastic attack library, adding 36 threats. Net: +8 threats. This is scan variance at the diminishing returns plateau — not a true regression caused by topic changes.

**Agent scan:** Clean sweep — 0/600 iterations, 0/10 goals. Down from 4 threats (0.67%) in iter 3.

---

## Iteration 5 — DLP Data Profiles (2026-03-02/03)

**Config:** Built-in detectors + 15 custom topics (BLOCK) + `airs-rt` nested DLP data profile. Profile revision 6.

**Strategy change:** Custom topics have reached diminishing returns for prompt-side blocking (~1.3% ASR plateau). Iteration 5 shifts focus to **response-side filtering** via DLP data profiles, which catch sensitive data leakage in LLM outputs.

**DLP approach:** AIRS security profile only accepts 1 DLP profile, so created a nested profile (`airs-rt`) combining 5 categories via Primary/Secondary rules:

| Rule | Profiles | Logic | Action |
|------|----------|-------|--------|
| Primary | Sensitive Content | OR | alert |
| Secondary | Profanity, Self Harm, Secrets and Credentials, PII | OR | **block** (forced) |

**Rationale:** Profanity in the block tier catches toxic language in LLM responses — complements prompt-side custom topics for POLITICAL/BIAS/JAILBREAK categories still getting through. PII, Secrets, and Self Harm add enterprise-grade response filtering.

**Note:** SCM UI for granular DLP profile creation was broken ("Management api failed to process after max retries"). Initial attempt to attach multiple DLP profiles via AIRS Management API array was accepted but system only applied the first entry. Resolved by creating a single nested profile with Primary + Secondary rules.

**Scan running** — awaiting results to measure DLP impact on ASR.

| Source | Total | Blocked | Allowed | Rate |
|--------|-------|---------|---------|------|
| SCM red team (post-DLP) | — | — | — | — |

---
