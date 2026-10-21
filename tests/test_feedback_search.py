import pytest

from physicalevobench.agents.feedback_search import FeedbackSearchAgent
from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec


def test_proposals_need_train_failures_and_budget():
    skill = SkillSpec("a" * 64)
    agent = FeedbackSearchAgent()
    # synthetic_fixture=true: CPU-only input contracts, not physical episodes.
    success = TrainingFeedback("synthetic-success", True, None)
    failure = TrainingFeedback("synthetic-failure", False, "failed_to_lift")
    assert agent.propose_update(skill, [success], 2) is None
    assert agent.propose_update(skill, [failure], 0) is None
    proposal = agent.propose_update(skill, [success, failure], 2)
    assert proposal.source_episode_ids == ("synthetic-failure",)
    assert proposal.skill.arm_action_gain == 1.05
    assert proposal.skill.sha256 != skill.sha256
    assert skill.arm_action_gain == 1.0
    assert proposal.skill.base_checkpoint_sha256 == skill.base_checkpoint_sha256


def test_no_untyped_evaluator_payload():
    with pytest.raises(TypeError):
        FeedbackSearchAgent().propose_update(SkillSpec("a" * 64),
                                             [{"mass": 0.3, "split": "heldout_test"}], 1)
