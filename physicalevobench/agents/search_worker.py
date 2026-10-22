"""Train-only sequential proposals; one JSON request per short-lived process."""

import json
import random
import sys

from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec

GRID = (0.85, 0.9, 0.95, 1.05, 1.1, 1.15)


def select(history):
    # Original wins all success ties. Candidate ties prefer the smaller intervention.
    return max(range(len(history)), key=lambda i: (
        sum(f["success"] for f in history[i]["feedback"]),
        -abs(history[i]["skill"]["arm_action_gain"] - 1), -i))


def respond(request):
    if set(request) != {"agent", "rng_seed", "history", "remaining_budget"}:
        raise ValueError("Unexpected search fields")
    if request["agent"] not in {"feedback", "random"}:
        raise ValueError("Unknown agent")
    if type(request["rng_seed"]) is not int or type(request["remaining_budget"]) is not int:
        raise ValueError("Invalid budget or RNG seed")
    history = request["history"]
    if not 1 <= len(history) <= 4:
        raise ValueError("Expected original and at most three trials")
    count = None
    for entry in history:
        if set(entry) != {"skill", "feedback"}:
            raise ValueError("Unknown trial fields")
        SkillSpec.from_dict(entry["skill"])
        feedback = [TrainingFeedback.from_payload(f) for f in entry["feedback"]]
        if not feedback or (count is not None and count != len(feedback)):
            raise ValueError("Paired nonempty training required")
        count = len(feedback)
    selected = select(history)
    gain = None
    trial = len(history) - 1
    if trial < 3:
        if request["remaining_budget"] < count:
            raise ValueError("Insufficient candidate rollout budget")
        if request["agent"] == "random":
            gain = random.Random(request["rng_seed"]).sample(GRID, 3)[trial]
        elif trial < 2:
            gain = (0.9, 1.1)[trial]
        else:
            scores = [sum(f["success"] for f in h["feedback"]) for h in history]
            side = 1 if scores[1] >= scores[2] else 2
            gain = (0.85 if side == 1 else 1.15) if scores[side] > scores[0] else (
                0.95 if side == 1 else 1.05)
    failures = [f["episode_id"] for h in history for f in h["feedback"] if not f["success"]]
    return {"next_gain": gain, "selected_index": selected, "source_failure_ids": failures,
            "feedback_used_for_proposal": request["agent"] == "feedback" and trial == 2}


def main():
    try:
        print(json.dumps(respond(json.load(sys.stdin)), allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
