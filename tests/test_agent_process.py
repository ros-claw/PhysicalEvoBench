import json
import subprocess
import sys

import pytest

from physicalevobench.protocols.skill import SkillSpec


@pytest.mark.parametrize("extra", [{"split": "heldout_test"}, {"object_mass_kg": 0.3}])
def test_process_refuses_test_or_physical_truth(extra):
    request = {"skill": SkillSpec("a" * 64).to_dict(), "remaining_budget": 1,
               "training_feedback": [{"episode_id": "synthetic-fixture", "success": False,
                                      "failure_type": None, **extra}]}
    result = subprocess.run([sys.executable, "-m", "physicalevobench.agents.worker"],
                            input=json.dumps(request), text=True, capture_output=True, timeout=10)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error" in json.loads(result.stderr)


def test_process_returns_revalidatable_hashed_candidate():
    request = {"skill": SkillSpec("a" * 64).to_dict(), "remaining_budget": 1,
               "training_feedback": [{"episode_id": "synthetic-fixture", "success": False,
                                      "failure_type": "failed_to_lift"}]}
    result = subprocess.run([sys.executable, "-m", "physicalevobench.agents.worker"],
                            input=json.dumps(request), text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    proposal = json.loads(result.stdout)["proposal"]
    assert SkillSpec.from_dict(proposal["skill"]).sha256 == proposal["skill_sha256"]
