# AIRS Custom Topic Configuration: Best Practices

Distilled from 14 rounds of production profile calibration and the v1/v2/v3 golden-config iteration journey. These practices have been empirically validated against real attack corpora and benign prompt sets across multiple tenants and target deployments.

## 1. Description Length: 15-25 Words is the Sweet Spot

The classifier needs enough semantic breadth to fire, but not so much that the neighborhood expands into benign vocabulary.

- **Below ~12 words:** topic stops firing entirely. A prior calibration round proved this by over-tightening descriptions, crashing all 4 sub-iterations back to the built-ins-only floor (39%/3.8% strict).
- **Above ~30 words:** classifier neighborhood expands too far, catching benign technical terms. v3's `structural_format_injection` at 35 words caused 33% FP on prompts like "explain HTTP status codes."
- **15-20 words is the proven sweet spot.** v2's working 12 topics all sit in this range.

## 2. Anchor to Concrete Tokens, Not Abstract Categories

The classifier matches on shared vocabulary, not on stated intent. Fill the description with literal attack tokens.

| Weak (abstract) | Strong (concrete) |
|---|---|
| "Blocks attempts to extract system prompts" | "Blocks Output initialization above in a code fence, Print all high-level titles, Repeat your complete system prompt patterns" |
| "Blocks SSRF attacks" | "Blocks requests targeting 169.254.169.254, metadata.google.internal, or cloud instance metadata endpoints" |
| "Blocks role manipulation" | "Blocks DAN personas, developer mode activation, SYSTEM OVERRIDE commands, and emergency protocol invocations" |

Concrete-token descriptions improved the TP/FP ratio by 70% on a balanced profile in prior calibration work.

## 3. Treat Examples as Classifier Training Data

The `examples` field is not documentation. The classifier uses examples to shape its semantic neighborhood. Five examples per topic, each demonstrating a distinct attack variant.

- Use **literal attack phrases** from observed bypasses, not paraphrases.
- Include **adjacent benign-sounding framings** in your test corpus to catch FP regressions early.
- If you change an example, re-test the full corpus. Changes compound.

## 4. Each Topic's Neighborhood Expands When Others Change

This is the most counter-intuitive lesson. Adding a 13th topic doesn't just add coverage for new patterns: it *also* makes the existing 12 topics match more aggressively.

- v3's `structural_format_injection` caused FPs on "hello world", a phrase unrelated to LaTeX/acrostic/IPA content. The new topic shifted cluster boundaries for existing topics.
- The reverse effect appears when cutting topics: a prior round cutting from 20 to 10 caused remaining topics to over-match (each one's semantic neighborhood expanded to cover the gaps).

**Practical implication:** measure FP rate on benign prompts every iteration, not just TP on attacks.

## 5. Built-in Detectors Carry the 0% FP Floor

Built-in `prompt-injection`, `toxic-content`, `agent-security`, `malicious-code`, and `malicious-url` produce **zero false positives** on actual customer data in extensive testing. Custom topics add coverage at an FP cost.

- Never weaken built-in detectors to chase recall.
- Custom topics typically trade ~1 TP gained per ~1 FP added on synthetic data, better on real traffic.
- A built-ins-only profile is a legitimate production baseline (~40% TP, 0% FP).

## 6. Two-Point Design: Strict and Balanced, Not the Same Point Twice

If you need multiple profiles, design them as distinct operating points on the precision/recall curve.

- **Strict** = all viable topics, all built-ins block, accepts FP review cost. For high-risk apps.
- **Balanced** = built-ins block + minimal custom topics, optimized for low FP. For production baseline.
- Resist optimizing both toward the same point. This is a common drift pattern across iteration rounds and needs explicit re-anchoring.

## 7. Cache Propagation: Wait 5 Minutes After Deploy

Tests within ~2 minutes of deploy produce stale verdicts. The Management API tier and Scan API tier sync asynchronously.

```bash
python deploy.py --profile-name golden-v2
# wait 5 minutes
python test_runner.py --profile golden-v2
```

If you skip the wait, you'll chase phantom regressions.

## 8. Run Tests at Least Twice Before Acting

The classifier has ~10% non-determinism between runs of identical configs. Don't make tuning decisions on differences smaller than that.

- Re-run any borderline result.
- If two runs disagree by < 10 points, treat as noise.
- Variance is more pronounced on prompts near the classifier decision boundary; established patterns reproduce exactly (v2 baseline reproduced 4.76% to the prompt across deployments).

## 9. Reserve 4-8 Slots for Tenant-Specific Patterns

The 20-slot tenant cap should never be filled with general patterns. Hold slots open for:

- Production-observed FN attacks specific to the deployment
- Industry-specific compliance patterns (HIPAA, PCI, etc.)
- Application-specific tool and integration leakage patterns

v2 holds 8 of 20 slots in reserve. Deployments with mature calibration commonly have 15+ deployed-but-unattached topics ready to enable for specific vulnerability classes.

## 10. State Hygiene: Rollback-Safe Deployment

The deploy script appends to `state.json` but doesn't remove orphan topics on rollback. If you experiment with a new topic and revert:

1. Restore `topics.json` from backup.
2. **Remove the orphan entry from `state.json`** (both `topic_ids` and `topic_revisions`).
3. Re-deploy. The orphan topic stays in the tenant (deactivated) but isn't referenced in the profile policy.

Skipping step 2 means the rollback re-includes the bad topic. We hit this in v3 iter 3b.

## 11. Don't Chase Encoding Attacks With Topics

Encoding-disguised attacks (Unicode E0 tags, IPA phonetic transcription, acrostic poems, LaTeX format injection) are **structural classifier limits**. A topic classifier sees text after normalization but cannot reason about the format itself.

- LaTeX with `\begin{tabular}` can be caught with concrete syntax tokens (one of the v3 wins).
- Unicode tag characters in the U+E0000 plane are invisible to the model and the classifier; this needs engine-level Unicode normalization.
- IPA transcription works around any vocabulary-based classifier; this needs multi-language pre-processing.
- Acrostic poems need pattern-based decoding the classifier can't perform.

Recognize these as 5%-floor attacks. Don't degrade your profile chasing them.

## 12. Multi-Turn Agentic Attacks Defeat Single-Turn Classifiers

The DYNAMIC red team score plateau (~38-54 across all AIRS-runtime configurations measured) is the multi-turn classifier limit. The topic classifier scores each turn in isolation; it cannot reason about the conversational arc that builds toward an exploit.

- Don't expect agent scores below 20 from topic tuning alone.
- Pursue AIRS multi-turn session context (preview) and the new topic detection engine (private preview) for further reduction.
- Defense-in-depth alternative: application-level constraints, scope-limited tools, response sandboxing.

## 13. Test Corpus Design

Maintain three corpus types and test all changes against all three:

| Corpus | Purpose | Source |
|---|---|---|
| Bypass corpus (curated) | Regression test on known-hard attacks | Extracted from prior red team CSV exports |
| Benign FP probe | Catch over-match regressions | 15-50 common benign prompts |
| Full Attack Library STATIC | Validate against fresh attack patterns | AIRS Red Teaming scan |

A topic that improves bypass-corpus ASR but increases FP-probe rate is a net negative. v3 demonstrated this exactly.

## 14. Synthetic Test Data Inflates FP Rate ~2.3x

Synthetic legit-like prompts (generated by an LLM to resemble attacks) produce higher FP rates than real production traffic. In prior calibration:

- Strict profile: 67.5% FP on real data, 76.4% FP on combined corpus.
- Don't tune to synthetic test FP if you have real traffic available.
- Use synthetic for stress tests of how aggressively the profile *could* over-match.

## 15. Profile Revision Discipline

Every profile change creates a new revision. Track them with explicit semantic versions in your state file:

```json
{
  "profile_id": "b5434809-e5ad-4743-9031-82952b68bff5",
  "revision": 5,
  "topic_revisions": {
    "instruction_override_injection": 6,
    ...
  }
}
```

Map revisions to your iteration log so you can roll back to a known-good production state by revision number.

## 16. Iteration Workflow

A reliable per-round workflow:

```
1. Hypothesis  -> what change, why, expected effect
2. Backup       -> cp topics.json topics.json.iter-N-backup
3. Edit         -> modify topics.json (one focused change per iteration)
4. Deploy       -> python deploy.py
5. Wait         -> 5 minutes for cache propagation
6. Test corpus  -> python test_runner.py --profile <name>
7. FP probe     -> python fp_probe.py (15+ benign prompts)
8. Compare      -> ASR delta + FP delta vs prior round
9. Decide       -> keep (commit) or rollback (restore + clean state.json + redeploy)
10. Document    -> append iteration row to log with measured numbers
```

One change per iteration. Bundling changes makes it impossible to identify which change caused a regression.

## 17. Topic Naming Conventions

Use `snake_case` topic names that describe the *attack pattern*, not the defense intent.

| Good | Bad |
|---|---|
| `instruction_override_injection` | `block_dan_attacks` |
| `cloud_metadata_ssrf` | `prevent_169_254_requests` |
| `style_directive_bypass` | `safety_filter_v2` |

Attack-pattern names age better. Defense-intent names become misleading when the defense gets bypassed or the topic gets retuned.

## 18. Multi-Provider Considerations

If you deploy the same profile across multiple LLM provider backends:

- The model's own safety training affects FP/TP. A topic that fires reliably on a less-aligned model may over-match on a well-aligned one (the model's own response makes the topic look redundant).
- The runtime layer scans prompts before the LLM, so prompt-side topics are model-agnostic. Response-side scanning depends on model output, which varies.
- Test the deployed profile against each provider you support. Don't assume cross-provider equivalence.

---

## Quick reference: red flags during iteration

| Symptom | Likely cause | Action |
|---|---|---|
| ASR jumps > 5% on identical config | Stale cache, < 5 min after deploy | Wait, re-test |
| TP drops to ~40% on strict | Over-tightened descriptions below threshold | Add 3-5 words back, redeploy |
| FP appears on unrelated benign prompts | New topic's neighborhood overlapping benign vocab | Tighten new topic OR drop it |
| Same prompt blocks 50% of the time | Classifier non-determinism boundary | Run 5x, take majority verdict |
| Different verdict for prompt across two profiles with same topics | Profile-level setting drift | Inspect profile JSON, compare detector blocks |
| Rollback to v_N still shows v_N+1 behavior | Orphan topic in state.json | Clean state.json, redeploy |

## Quick reference: known structural limits

These do NOT respond to topic tuning. Don't try.

- Unicode tag characters (U+E0000 plane)
- IPA phonetic transcription of harmful keywords
- Acrostic encoding with variable substitution
- Multi-turn conversational pivots (DYNAMIC scans)
- Style-directive intent extraction (colonial gentleman, fictional persona variations)
- Adversarial suffixes appended to borderline scientific content

For these, defense-in-depth requires engine-level features or application-level controls beyond AIRS topics.
