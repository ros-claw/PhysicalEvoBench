# Raw final-policy diagnosis after retention-gate failures

**Main confirmation outcome remains `STABLE_SELF_EVOLUTION_NOT_ESTABLISHED`.**

This separately registered diagnostic compares every trajectory's latest raw round-3 candidate to the original and latest raw restart candidate. It adds no training and overrides no promotion. It cannot rescue the failed main stability confirmation.

[Protocol](RAW_POLICY_PROBE_PROTOCOL_20261024.md). [Main results](STABILITY_RESULTS_20261024.md). [Raw evidence manifest](../evidence/raw-policy-probe-20261024/manifest.json).

| Trajectory | Original /64 | Raw continual /64 | Latest raw restart /64 |
| --- | --- | --- | --- |
| 0 | 16 | 32 | 27 |
| 1 | 11 | 28 | 24 |
| 2 | 19 | 8 | 17 |

| Comparison | Official-success difference (pp) | Adjusted conditional interval (pp) |
| --- | --- | --- |
| raw_continual_vs_frozen | +11.46 | [+0.52, +22.40] |
| raw_restart_vs_frozen | +11.46 | [+2.08, +21.35] |
| raw_continual_vs_raw_restart | +0.00 | [-10.94, +10.94] |

10,000 paired condition-bootstrap draws within three fixed learned trajectories, Bonferroni alpha=0.05/3. These intervals do not establish population-level stability or a safety guarantee. The restart arm is the last candidate, not a best-of-three oracle.

| Trajectory | Raw arm | Original / new violation samples | Original / new exposure | Per-joint depth margin passes |
| --- | --- | --- | --- | --- |
| 0 | raw_continual | 159 / 105 | 114102 / 104031 | False |
| 0 | raw_restart | 159 / 8 | 114102 / 98955 | True |
| 1 | raw_continual | 176 / 83 | 120357 / 119601 | True |
| 1 | raw_restart | 176 / 161 | 120357 / 106263 | False |
| 2 | raw_continual | 146 / 63 | 105840 / 123039 | False |
| 2 | raw_restart | 146 / 70 | 105840 / 115704 | False |

Two raw continual trajectories improved point success, while the third fell from 19/64 to 8/64. Raw continual and latest raw restart both scored 68/192; their adjusted conditional interval includes gains and losses. The per-joint depth guard failed in two of three raw continual trajectories. These observations distinguish task learning, inconsistent transfer and variable safety checks; they do not override any private promotion. Sustained holding, contact safety, future learning seeds and indefinite self-improvement are not established.

Cost: 576 actual evaluation episodes on 192 unique paired conditions, zero new optimizer iterations. All nine checkpoint assignments froze before the first launch; no extra GPU process ran during the primary confirmation. Per-policy native processes, raw physical readbacks/actions/outcomes, matched initial observations and sampled safety were independently audited. No checkpoint weights are distributed.
