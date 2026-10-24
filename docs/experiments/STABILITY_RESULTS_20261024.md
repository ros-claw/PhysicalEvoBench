# Three-seed, three-round stable adaptation confirmation

**Stable self-evolution was not established.**
This is a completed fixed-budget physical experiment; CPU fixtures and diagnostics are not scored as learned improvement.

[Preregistered protocol](STABILITY_PROTOCOL_V3_20261024.md). [Complete archive manifest](../evidence/stability-20261024/manifest.json).

Source: `7fbd96ed40ad59b419ac9ce5a526bbdea310425e`. All final heldout policies were frozen at `2026-10-24T14:55:38.067723+00:00` before heldout launches.

## Independent heldout results

Each learning seed uses 128 fresh paired mass/seed conditions, evaluated in separate policy processes. Cells are official upstream lift successes out of 128. Success termination and the official predicate are unchanged. All arms share a numerical action envelope of +/-1000 raw action units. This is not a physical safety guarantee. Sustained holding is NOT_MEASURED in these early-terminating episodes.

| Learning seed | Frozen | Identity replay | Retained round 1 | Retained round 2 | Retained round 3 | Equal-budget restart |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 34 | 32 | 36 | 32 | 36 | 36 |
| 1 | 29 | 35 | 32 | 31 | 34 | 57 |
| 2 | 24 | 26 | 21 | 25 | 23 | 27 |

Different outcomes from identical retained checkpoint hashes are replay variability, not learning. Raw candidate updates and private promotion decisions are reported separately.

| Registered comparison | Official success difference (pp) | Adjusted interval (pp) | Alpha |
| --- | --- | --- | --- |
| round1_vs_frozen | +0.52 | [-4.95, +5.99] | 0.008333 |
| round1_vs_identity | -1.04 | [-5.99, +3.91] | 0.008333 |
| round2_vs_frozen | +0.26 | [-4.43, +4.95] | 0.008333 |
| round2_vs_identity | -1.30 | [-5.73, +3.12] | 0.008333 |
| round3_vs_frozen | +1.56 | [-3.65, +6.77] | 0.008333 |
| round3_vs_identity | +0.00 | [-4.95, +4.95] | 0.008333 |
| round2_vs_previous | -0.26 | [-3.91, +3.39] | 0.025000 |
| round3_vs_previous | +1.30 | [-2.34, +4.95] | 0.025000 |
| final_vs_restart | -7.03 | [-11.20, -2.86] | 0.050000 |

Intervals use 10,000 paired condition-bootstrap draws stratified by the three fixed learned trajectories. They do not establish a population-level guarantee over future learning seeds. The six frozen-control comparisons use Bonferroni alpha=0.05/6; consecutive non-regression uses alpha=0.05/2 and a -5 pp tolerance. Bootstrap coverage is approximate.

## Registered scientific gates

| Gate | Passed |
| --- | --- |
| all_rounds_beat_both_frozen_controls | False |
| each_seed_final_gain_positive | False |
| consecutive_nonregression | False |
| two_actual_promotions_each_seed | False |
| sampled_safety_guards | False |

Superiority to this particular equal-budget restart control: **False**.

## Training, private validation and actual retained changes

Every round trained for 614,400 real transitions. Continual training always resumed the preceding raw candidate; restart training always loaded the original. The learner selected its next rate from training rewards only. Private validation never selected the next training checkpoint.

| Seed | Lane | Round | Incumbent / candidate official successes (of 64) | Promoted | Candidate SHA256 |
| --- | --- | --- | --- | --- | --- |
| 0 | continual | 1 | 17 / 19 | False | `3723f05d48f932afe585f9ddf81d1d5d3baef0ed25a07c3f9f9c23e94e08cb09` |
| 0 | continual | 2 | 13 / 18 | False | `b3f567976866378c419f31cb0fac0a0040935a492e21d8f9f2bf81ee69939a27` |
| 0 | continual | 3 | 15 / 33 | False | `b9214dad824031c33f345d6df996a49623b9ae5d17f2a967ddc5341f26f233b8` |
| 0 | restart | 1 | 15 / 16 | False | `6cb3118bf50ddcee841555b3d9ff3bdbe10ef54b061077b6d0fb6ba92ad9db8d` |
| 0 | restart | 2 | 12 / 12 | False | `5174821de915404b244d9bd4e09114366f58bc771c4b0e8e91eda872a05d8967` |
| 0 | restart | 3 | 13 / 30 | False | `7c613c2128bce5ddcfc3490c28c7b3f362e3cf1b1fcd0ce2920e817ffc788201` |
| 1 | continual | 1 | 14 / 15 | False | `53b096247de10f566cb920ba094d5262bd2cd66ed3dde25c9fdc6d7cb8de50d8` |
| 1 | continual | 2 | 15 / 17 | False | `77ef32cf33eb9aec1d290ebcfb60686161a4ecee164b8980109c0beffa6eba38` |
| 1 | continual | 3 | 10 / 23 | False | `2037bfae4e73c295b4fb716c767e09c4bb19732f63e0389769953eb60657b5a4` |
| 1 | restart | 1 | 10 / 25 | False | `4a047eddd06cff51f3d803ef36d0e6ef99a925816c5c4d93efa27f3c22266512` |
| 1 | restart | 2 | 17 / 16 | False | `ebb9d331f6a7e0110cb3707c32ad841d27de9fd89d0bbe64508173864382b983` |
| 1 | restart | 3 | 14 / 25 | True | `a0250bf52ce6ae9eb49d869663172b1e06935aa18bdd34b58d519a10369dc8ad` |
| 2 | continual | 1 | 11 / 22 | False | `d2ec3a72cb49f155f95518306d47e51a4467b9b124a1a653b55781804cf745c6` |
| 2 | continual | 2 | 13 / 23 | False | `75f441333532c0c131d66e690363c9e6146de6401ab3fe9366730b76ac04112b` |
| 2 | continual | 3 | 15 / 14 | False | `2200621c19924dfe2603f5e1979c3f963f8d59d29d8859e59c41e48449f654a9` |
| 2 | restart | 1 | 18 / 11 | False | `d4f62ea5a33d2b6bbefd10201f7e08fa1e00982312def871d7bf0d64c4413dc3` |
| 2 | restart | 2 | 18 / 21 | False | `39287fc112639ade0b24aa731fbed102664a52985fb1e574a1204a8c705b6d0d` |
| 2 | restart | 3 | 18 / 18 | False | `0161c41044c18267d2eaf573bf7930968a61af16887a23a23839df69f3311386` |

Retained checkpoint SHA256 prefixes (full hashes are in the archive):

| Seed | Continual round 1 | Continual round 2 | Continual round 3 | Restart final |
| --- | --- | --- | --- | --- |
| 0 | `babbbfd363f8` | `babbbfd363f8` | `babbbfd363f8` | `babbbfd363f8` |
| 1 | `babbbfd363f8` | `babbbfd363f8` | `babbbfd363f8` | `a0250bf52ce6` |
| 2 | `babbbfd363f8` | `babbbfd363f8` | `babbbfd363f8` | `babbbfd363f8` |

## Sampled safety and replay diagnostics

These are pre-step joint-limit samples, with a 0.001 coordinate-unit tolerance; finger units are metres and arm units radians. Collision/contact safety and between-sample excursions remain unmeasured. Engineering acceptance margins are not a general safety guarantee.

| Seed | Arm | Joint violations / joint samples | Episodes with a violation | Worst finger depth (mm) |
| --- | --- | --- | --- | --- |
| 0 | frozen | 228 / 217854 | 36/128 | 47.318 |
| 0 | identity | 197 / 228186 | 41/128 | 35.301 |
| 0 | round1 | 175 / 215181 | 32/128 | 28.087 |
| 0 | round2 | 189 / 226845 | 34/128 | 32.362 |
| 0 | round3 | 180 / 218097 | 32/128 | 32.362 |
| 0 | restart | 228 / 224091 | 34/128 | 28.087 |
| 1 | frozen | 279 / 230436 | 40/128 | 23.110 |
| 1 | identity | 239 / 222849 | 33/128 | 26.215 |
| 1 | round1 | 265 / 231138 | 33/128 | 26.215 |
| 1 | round2 | 274 / 232452 | 43/128 | 24.977 |
| 1 | round3 | 350 / 225405 | 44/128 | 26.215 |
| 1 | restart | 116 / 214929 | 28/128 | 19.742 |
| 2 | frozen | 285 / 233541 | 43/128 | 28.717 |
| 2 | identity | 328 / 242262 | 42/128 | 25.433 |
| 2 | round1 | 308 / 247581 | 46/128 | 24.265 |
| 2 | round2 | 308 / 239211 | 40/128 | 28.717 |
| 2 | round3 | 279 / 240930 | 43/128 | 21.350 |
| 2 | restart | 262 / 234882 | 41/128 | 21.350 |

Supplemental exact one-sided sign-test diagnostics for final vs frozen (not replacements for registered bootstrap gates):

| Seed | Discordant wins | Discordant losses | Exact one-sided p |
| --- | --- | --- | --- |
| 0 | 11 | 9 | 0.41190147 |
| 1 | 11 | 6 | 0.16615295 |
| 2 | 9 | 10 | 0.67619705 |

## Process-block and identical-policy diagnostics

[Defined before heldout launch](STABILITY_ANALYSIS_SUPPLEMENT_20261024.md). These do not alter the registered primary decision. Whole blocks of 32 paired conditions are resampled within each learned trajectory to examine within-process correlation.

| Final comparison | Difference (pp) | Process-block interval (pp) | Paired blocks |
| --- | --- | --- | --- |
| final_vs_frozen | +1.56 | [-3.39, +6.25] | 12 |
| final_vs_identity | +0.00 | [-3.65, +3.12] | 12 |

Both supplemental process-block intervals exclude zero positively: **False**. A positive per-condition interval without process-block corroboration is not evidence robust to this different uncertainty assumption.

| Seed | Identical-policy safety replay passes | Failed guard components |
| --- | --- | --- |
| 0 | False | per_joint_depth |
| 1 | False | per_joint_depth |
| 2 | False | raw_count, normalized_count |

Identical model hashes can still yield different physical traces and sampled safety extremes. A failed replay guard exposes measurement variability; no rejected candidate is retroactively promoted.

| Seed | Block | Frozen | Identity | Round 1 | Round 2 | Round 3 | Restart |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 3 | 4 | 4 | 2 | 5 | 6 |
| 0 | 1 | 9 | 7 | 10 | 8 | 10 | 9 |
| 0 | 2 | 13 | 12 | 13 | 13 | 11 | 12 |
| 0 | 3 | 9 | 9 | 9 | 9 | 10 | 9 |
| 1 | 0 | 6 | 8 | 6 | 6 | 4 | 11 |
| 1 | 1 | 7 | 11 | 11 | 10 | 12 | 12 |
| 1 | 2 | 8 | 7 | 8 | 7 | 8 | 20 |
| 1 | 3 | 8 | 9 | 7 | 8 | 10 | 14 |
| 2 | 0 | 3 | 6 | 3 | 4 | 3 | 5 |
| 2 | 1 | 5 | 7 | 8 | 6 | 6 | 6 |
| 2 | 2 | 5 | 7 | 3 | 7 | 8 | 8 |
| 2 | 3 | 11 | 6 | 7 | 8 | 6 | 8 |

## Cost, integrity and interpretation

Independent delivery audit: **PASS**, 4,610 completed evaluation episodes across 217 native workers, 11,059,200 training transitions, 44,615 completed training episodes and 262,320 unfinished-rollout steps. Training completions do not count as evaluation successes. Earlier attempts consumed another 3,686,400 training transitions, four diagnostic episodes, 24 failed holding-calibration episodes and 24 official-calibration episodes. They are separately accounted, not successful replications.

**Earlier failures remain negative:** the v1 third continual seed overflowed its value loss at updates 112/113; all six first-round jobs and 14,892 completed training episodes are archived. The original policy reached the nominal goal 12/12 but held it at low speed for 0.30 s in 0/12 full-horizon calibration episodes; open-gripper scored 0/12 on both. v2 confirmation was blocked. The v3 primary metric was explicitly preregistered as the original official task before new training, rather than treating failed physical holding as success. See [v1 numerical failure archive](../evidence/stability-v1-numerical-failure-20261024/manifest.json).

The independent audit checks raw actions/states, upstream official completion records, the common numerical action envelope, sampled safety, physical mass readback, matching initial states/public observations/velocities, source/checkpoint lineage, reservations, optimizer audits and final statistics. No model weights are redistributed. Source archives, hashed transition chunks, process logs, failure records and all episode traces are retained.

A negative outcome distinguishes what failed in this fixed study: private promotion, heldout transfer, repeated-round gain, reproducibility or sampled safety. It does not prove the task unsolvable or all agents incapable. Even a positive result would support only bounded autonomous policy adaptation in this simulator, mass interval and five-second horizon; it would not prove unlimited or general self-evolution.

Recompute from unpacked evidence: `uv run python scripts/audit_stability_study.py --run-dir <study>`. Private per-job tensor and transition audit: Arena interpreter, `-m physicalevobench.calibration.training_audit --run-dir <train>`, requiring the separately licensed checkpoints.


## Separate raw-policy diagnosis and final verification

The [separately registered raw-final-policy diagnosis](RAW_POLICY_PROBE_RESULTS_20261024.md)
completed 576 more episodes without training or promotion overrides. Original
46/192, raw continual 68/192, latest raw restart
68/192. Raw continual vs original: +11.46 pp, adjusted
conditional interval [+0.52, +22.40] pp. The main
confirmation remains **STABLE_SELF_EVOLUTION_NOT_ESTABLISHED**. Per-trajectory raw continual counts are 16→32, 11→28 and 19→8 (each of 64); positive pooled conditional gain conceals a negative third trajectory. Raw continual and latest raw restart both score 68/192.

Final independent verification additionally binds every complete registered
condition (including seed and mass), per-worker budget and model assignment to
frozen training lineage, and checks diagnostic seed disjointness from the parent
study. It changes neither physics nor scientific criteria or results. Both the
original and strengthened verifier receipts and committed sources are archived.
[Failed validation joint-depth witnesses](../evidence/stability-20261024/validation_depth_witnesses.json)
are a post-hoc explanation of recorded decisions, with no decision changes.
