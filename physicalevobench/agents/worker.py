"""One JSON request on stdin, one JSON proposal on stdout; no environment access via RPC."""

import json
import sys
from dataclasses import asdict

from physicalevobench.agents.feedback_search import FeedbackSearchAgent
from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec


def main():
    try:
        request = json.load(sys.stdin)
        if set(request) != {"skill", "training_feedback", "remaining_budget"}:
            raise ValueError("Unexpected proposal request fields")
        budget = request["remaining_budget"]
        if type(budget) is not int or budget < 0:
            raise ValueError("Invalid remaining budget")
        skill = SkillSpec.from_dict(request["skill"])
        feedback = [TrainingFeedback.from_payload(row) for row in request["training_feedback"]]
        proposal = FeedbackSearchAgent().propose_update(skill, feedback, budget)
        response = {"proposal": None}
        if proposal:
            response = {"proposal": {**asdict(proposal), "skill": proposal.skill.to_dict(),
                                     "skill_sha256": proposal.skill.sha256}}
        print(json.dumps(response, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
