"""CPU contracts used by the trusted experiment runner."""

import math
import random
from dataclasses import dataclass


@dataclass
class Budget:
    limit: int
    used: int = 0

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in (self.limit, self.used)):
            raise ValueError("Budget values must be non-negative integers")
        if self.used > self.limit:
            raise ValueError("Budget exceeded")

    def reserve(self):
        # Reserve before launch: a crashed simulation still consumes an attempted rollout.
        if self.used >= self.limit:
            raise RuntimeError("Physical episode budget exhausted")
        self.used += 1


def build_manifests(seed, counts, mass_range):
    if set(counts) != {"train", "validation", "heldout_test"}:
        raise ValueError("Exactly three splits required")
    if any(type(n) is not int or n < 1 for n in counts.values()):
        raise ValueError("Each split needs a positive condition count")
    low, high = mass_range
    if not all(math.isfinite(v) for v in mass_range) or not 0 < low < high:
        raise ValueError("Invalid calibrated mass range")
    rng = random.Random(seed)
    result = {}
    seeds = set()
    for split in ("train", "validation", "heldout_test"):
        result[split] = []
        for i in range(counts[split]):
            episode_seed = rng.randrange(2**31)
            while episode_seed in seeds:
                episode_seed = rng.randrange(2**31)
            seeds.add(episode_seed)
            result[split].append({"condition_id": f"{split}-{i:05d}", "split": split,
                                  "seed": episode_seed, "object_mass_kg": rng.uniform(low, high)})
    return result


def promotion_gate(incumbent, candidate, min_gain=0.0):
    """Strict positive paired improvement; infra errors invalidate the gate."""
    if not math.isfinite(min_gain) or not 0 <= min_gain <= 1:
        raise ValueError("Invalid promotion threshold")
    if not incumbent or len(incumbent) != len(candidate):
        raise ValueError("Gate requires nonempty paired validation results")
    def index(rows):
        output = {}
        for row in rows:
            if row["split"] != "validation" or type(row["success"]) is not bool:
                raise ValueError("Invalid validation episode")
            if row["condition_id"] in output:
                raise ValueError("Duplicate validation condition")
            if row.get("execution_status") != "OK":
                raise ValueError("Infrastructure failure invalidates promotion")
            output[row["condition_id"]] = row["success"]
        return output
    old, new = index(incumbent), index(candidate)
    if old.keys() != new.keys():
        raise ValueError("Validation condition mismatch")
    gain = sum(int(new[k]) - int(old[k]) for k in old) / len(old)
    return {"decision": "promote" if gain > min_gain else "rollback", "paired_gain": gain,
            "min_gain": min_gain, "num_pairs": len(old)}
