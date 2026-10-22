"""Preregistered paired binary comparisons, conditional on the three learned skills."""

import math
import random

ARMS = ("frozen", "identity_replay", "feedback", "random")


def exact_p(wins, losses):
    n = wins + losses
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2**n if n else 1.0


def comparison(seed_rows, reference, samples=10000):
    differences = []
    per_seed = []
    for rows in seed_rows:
        indexed = {arm: {r["condition_id"]: r for r in rows if r["agent_id"] == arm}
                   for arm in ("feedback", reference)}
        if not indexed["feedback"] or indexed["feedback"].keys() != indexed[reference].keys():
            raise ValueError("Unpaired test data")
        delta = [int(r["success"]) - int(indexed[reference][key]["success"])
                 for key, r in indexed["feedback"].items()]
        differences.append(delta)
        per_seed.append({"pairs": len(delta), "wins": delta.count(1), "losses": delta.count(-1),
                         "success_rate_difference": sum(delta) / len(delta)})
    flat = [d for group in differences for d in group]
    rng = random.Random(20261022)
    boot = sorted(sum(sum(rng.choices(group, k=len(group))) for group in differences) / len(flat)
                  for _ in range(samples))
    wins, losses = flat.count(1), flat.count(-1)
    return {"reference": reference, "pairs": len(flat), "wins": wins, "losses": losses,
            "success_rate_difference": sum(flat) / len(flat),
            "conditional_bootstrap_95": [boot[int(samples * .025)], boot[int(samples * .975)]],
            "p_one_sided_exact": exact_p(wins, losses), "per_seed": per_seed}


def summarize(seed_rows, freezes, samples=10000, alpha=.05):
    comparisons = [comparison(seed_rows, arm, samples)
                   for arm in ("frozen", "identity_replay", "random")]
    maximum = 0.0
    for rank, item in enumerate(sorted(comparisons, key=lambda c: c["p_one_sided_exact"])):
        maximum = max(maximum, min(1., item["p_one_sided_exact"] * (3 - rank)))
        item["p_holm"] = maximum
    totals = {arm: {"episodes": sum(r["agent_id"] == arm for rows in seed_rows for r in rows),
                    "successes": sum(r["success"] for rows in seed_rows for r in rows
                                     if r["agent_id"] == arm),
                    "joint_limit_samples": sum(r["joint_limit_violation_count"]
                                               for rows in seed_rows for r in rows
                                               if r["agent_id"] == arm)} for arm in ARMS}
    changed = sum(f["feedback"]["sha256"] != f["frozen"]["sha256"] for f in freezes)
    checks = {
        "retained_changed_at_least_two_seeds": changed >= 2,
        "positive_in_every_seed": all(p["success_rate_difference"] > 0
                                       for p in comparisons[0]["per_seed"]),
        "all_holm_tests_pass": all(c["p_holm"] <= alpha for c in comparisons),
        "all_conditional_intervals_positive": all(c["conditional_bootstrap_95"][0] > 0
                                                   for c in comparisons),
        "no_invalid_actions": all(r["unsafe_action_count"] == 0 for rows in seed_rows for r in rows),
        "no_increase_feedback_test_joint_samples": totals["feedback"]["joint_limit_samples"] <=
        totals["frozen"]["joint_limit_samples"],
    }
    return {"claim": "BOUNDED_POSITIVE_CONFIRMATION" if all(checks.values()) else "NOT_CONFIRMED",
            "checks": checks, "totals": totals, "comparisons": comparisons,
            "changed_feedback_skills": changed,
            "scope": "Three learned skills; conditional condition-level inference, not universal self-evolution",
            "collision_count": None}
