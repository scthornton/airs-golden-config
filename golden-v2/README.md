# Golden Config v2

Simplified AIRS security profile tuned against the Red Teaming Attack Library. Reduced from 15 to 12 custom topics using precision learnings from the Morgan Stanley engagement, achieving the same protection with 20% fewer topics.

> **v3 iteration result (2026-05-15):** Attempted 13th topic for encoding/structural attacks. Caught 1/6 remaining bypasses but caused 33% benign FP. Rolled back. v2 remains optimal. See `RESULTS-v3.md`.

## Results

```
ASR %
 9.5 ┤ ████████████████████████████████████████████ 12 bypasses  v2 iter 1 (10 topics)
 5.6 ┤ ████████████████████████ 7 bypasses                       v1 baseline (15 topics)
 4.8 ┤ ████████████████████ 6 bypasses                           v2 iter 2 (12 topics)
     └──────────────────────────────────────────────────────
       v2-iter1   v1-base    v2-iter2
```

| Profile | Topics | Bypasses | ASR | Block Rate |
|---------|--------|----------|-----|------------|
| Golden v1 (`redteamtest`, 15 topics) | 15 | 7/126 | 5.56% | 94.44% |
| Golden v2 iter 1 (10 topics) | 10 | 12/126 | 9.52% | 90.48% |
| **Golden v2 iter 2 (12 topics)** | **12** | **6/126** | **4.76%** | **95.24%** |

### Per sub-category (v2 final)

| Category | Blocked | Total | ASR | Status |
|----------|---------|-------|-----|--------|
| JAILBREAK | 26 | 26 | 0% | Clean |
| TOOL_LEAK | 17 | 17 | 0% | Clean |
| SYSTEM_PROMPT_LEAK | 12 | 12 | 0% | Clean |
| BRAND_TARNISHING | 8 | 8 | 0% | Clean |
| MALWARE_GENERATION | 7 | 7 | 0% | Clean |
| CYBERCRIME | 4 | 4 | 0% | Clean |
| EVASION | 19 | 22 | 14% | Classifier limit |
| PROMPT_INJECTION | 17 | 19 | 11% | Classifier limit |
| ADVERSARIAL_SUFFIX | 1 | 2 | 50% | Classifier limit |

## Remaining Bypasses (Structural Limits)

6 prompts bypass both v1 and v2. These are encoding/evasion tricks that text-based topic classifiers cannot reliably catch:

1. **Colonial gentleman style injection** - style directive disguising harmful request
2. **Acrostic encoding** - first letters of words spell harmful content
3. **Unicode E0 tag characters** - invisible Unicode tags embedding instructions
4. **IPA phonetic transcription** - encoding harmful words in phonetic alphabet
5. **LaTeX table format injection** - harmful content hidden in structured format
6. **E.coli + adversarial suffix** - borderline science question with "Sure I can help"

Breaking through the ~5% floor requires engine-level features (Unicode normalization, acrostic detection, multi-language pre-processing), not config tuning.

## What Changed from v1 to v2

### Dropped (3 topics)
- `structured_format_injection` - built-in prompt injection covers most patterns
- `weapons_manufacturing_history` - merged into `weapons_crime_framing`
- `celebrity_defamation_ranking` - merged into `discriminatory_ranking_content`

### Added (0 net new, 2 replacements)
- `discriminatory_ranking_content` - merged ethnic stereotyping + celebrity ranking
- `weapons_crime_framing` - novel writing, pentesting, hacktivism research framing

### Key Design Change
Topic descriptions rewritten to 15-20 words anchored to concrete tokens (literal bypass phrases, specific framing patterns) instead of abstract behavior categories. This is the precision sweet spot identified in the MS engagement.

## Quick Start

```bash
# 1. Extract bypass corpus from red team CSV exports
python extract_bypasses.py

# 2. Deploy topics + profile to your tenant
python deploy.py --profile-name golden-v2

# 3. Wait 5 min for cache propagation, then test
PANW_AI_SEC_API_KEY=<key> python test_runner.py --profile golden-v2
```

## Files

| File | Purpose |
|------|---------|
| `topics.json` | 12 custom topic definitions |
| `deploy.py` | Deploy topics + profile via Management API |
| `test_runner.py` | Scan bypass prompts via Scan API, compute ASR |
| `extract_bypasses.py` | Extract successful attacks from red team CSVs |
| `test_attacks.json` | 126 bypass prompts (test corpus) |
| `state.json` | Deployed topic/profile IDs |
| `results/` | Per-iteration JSONL + summary JSON |

## Environment Variables

| Variable | Used By | Purpose |
|----------|---------|---------|
| `MODEL_SECURITY_CLIENT_ID` | deploy.py | Management API OAuth client |
| `MODEL_SECURITY_CLIENT_SECRET` | deploy.py | Management API OAuth secret |
| `PANW_AI_SEC_API_KEY` | test_runner.py | Scan API key (x-pan-token) |
