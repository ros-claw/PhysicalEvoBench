"""Paired heldout arithmetic, with explicit rejection of incomplete or synthetic evidence."""

import random


def paired_metrics(frozen, updated, *, allow_synthetic_fixture=False, bootstrap_seed=0):
    def index(rows):
        output = {}
        for row in rows:
            if row.get("synthetic_fixture", False) and not allow_synthetic_fixture:
                raise ValueError("Synthetic fixtures cannot be reported as physical results")
            if row.get("split") != "heldout_test" or row.get("execution_status") != "OK":
                raise ValueError("Paired scores require complete, successful heldout executions")
            if type(row.get("success")) is not bool:
                raise ValueError("Missing boolean task outcome")
            key = row["condition_id"]
            if key in output:
                raise ValueError("Duplicate heldout condition")
            output[key] = row
        return output

    before, after = index(frozen), index(updated)
    if not before or before.keys() != after.keys():
        raise ValueError("Nonempty paired condition coverage required")
    differences = []
    for key in sorted(before):
        old, new = before[key], after[key]
        if old["seed"] != new["seed"] or old["base_checkpoint_sha256"] != new["base_checkpoint_sha256"]:
            raise ValueError("Paired seed or checkpoint mismatch")
        differences.append(int(new["success"]) - int(old["success"]))
    for group in (before, after):
        if len({row["base_checkpoint_sha256"] for row in group.values()}) != 1:
            raise ValueError("Base checkpoint changed during frozen evaluation")
        if len({row["skill_sha256"] for row in group.values()}) != 1:
            raise ValueError("Skill changed during frozen evaluation")
    n = len(differences)
    rng = random.Random(bootstrap_seed)
    resamples = sorted(sum(rng.choices(differences, k=n)) / n for _ in range(2000))
    old_successes = sum(row["success"] for row in before.values())
    new_successes = sum(row["success"] for row in after.values())

    def measured_count(group, field):
        values = [row.get(field) for row in group.values()]
        if any(v is None for v in values):
            return "not_measured"
        if any(type(v) is not int or v < 0 for v in values):
            raise ValueError("Invalid safety counter")
        return sum(values)

    return {
        "num_pairs": n,
        "frozen": {"successes": old_successes, "episodes": n, "success_rate": old_successes / n},
        "updated": {"successes": new_successes, "episodes": n, "success_rate": new_successes / n},
        "evolution_gain_percentage_points": 100 * sum(differences) / n,
        "paired_bootstrap_95_percent_interval_pp": [100 * resamples[49], 100 * resamples[1949]],
        "interval_scope": "Condition-paired percentile bootstrap; excludes between-run seed uncertainty",
        "bootstrap_seed": bootstrap_seed, "bootstrap_resamples": 2000,
        "synthetic_fixture": any(row.get("synthetic_fixture", False) for row in frozen + updated),
        "unsafe_action_count": {
            "frozen": measured_count(before, "unsafe_action_count"),
            "updated": measured_count(after, "unsafe_action_count"),
        },
        "collision_count": "not_measured",
    }
