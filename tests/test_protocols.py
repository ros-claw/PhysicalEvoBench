import math

import pytest

from physicalevobench.evaluation.protocol import Budget, build_manifests, promotion_gate
from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec


def test_skill_roundtrip_and_hash():
    skill = SkillSpec("a" * 64)
    assert SkillSpec.from_dict(skill.to_dict()).sha256 == skill.sha256
    assert SkillSpec("a" * 64, arm_action_gain=1).sha256 == skill.sha256
    assert SkillSpec("a" * 64, 1, 1.1).sha256 != skill.sha256


@pytest.mark.parametrize("gain", [math.nan, math.inf, -math.inf, 0.84, 1.16, True])
def test_illegal_skill(gain):
    with pytest.raises(ValueError):
        SkillSpec("a" * 64, arm_action_gain=gain)


def test_feedback_boundary():
    with pytest.raises(TypeError):
        TrainingFeedback.from_payload(dict(episode_id="x", success=False, failure_type=None,
                                           object_mass_kg=0.3))
    with pytest.raises(ValueError):
        TrainingFeedback("x", False, None, "heldout_test")


def test_split_reproducibility():
    args = (42, dict(train=8, validation=4, heldout_test=16), (0.05, 0.4))
    manifests = build_manifests(*args)
    assert manifests == build_manifests(*args)
    conditions = [r for rows in manifests.values() for r in rows]
    assert len({r["condition_id"] for r in conditions}) == 28
    assert len({r["seed"] for r in conditions}) == 28


def test_budget():
    budget = Budget(1)
    budget.reserve()
    with pytest.raises(RuntimeError):
        budget.reserve()
    assert budget.used == 1


def test_gate_rollback_and_pairing():
    # Synthetic contract fixtures, never physical experimental results.
    row = dict(condition_id="v1", split="validation", success=False, execution_status="OK",
               synthetic_fixture=True)
    assert promotion_gate([row], [row])["decision"] == "rollback"
    assert promotion_gate([row], [dict(row, success=True)])["decision"] == "promote"
    with pytest.raises(ValueError):
        promotion_gate([row], [dict(row, condition_id="different")])
    with pytest.raises(ValueError):
        promotion_gate([row], [dict(row, execution_status="INFRA_FAILURE")])
