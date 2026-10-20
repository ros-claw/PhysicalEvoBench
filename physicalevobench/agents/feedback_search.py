"""Conservative deterministic proposals from permitted training failures."""

from physicalevobench.protocols.agent import SkillProposal
from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec


class FeedbackSearchAgent:
    def propose_update(self, current_skill, training_feedback, remaining_budget):
        if type(remaining_budget) is not int or remaining_budget < 0:
            raise ValueError("Remaining physical budget must be a non-negative integer")
        if not all(isinstance(f, TrainingFeedback) for f in training_feedback):
            raise TypeError("Agent only accepts serialized training feedback contracts")
        failures = [f for f in training_feedback if not f.success]
        if not failures or remaining_budget <= 0:
            return None
        # A hypothesis, not a known optimum. Only physical train/validation may select it.
        gain = round(current_skill.arm_action_gain + 0.05, 6)
        if gain > 1.15:
            return None
        return SkillProposal(
            skill=SkillSpec(current_skill.base_checkpoint_sha256,
                            current_skill.skill_version + 1, gain),
            source_episode_ids=tuple(f.episode_id for f in failures),
            hypothesis="Training task failures observed; test a bounded increase in joint-position "
                       "action gain. Causal diagnosis and improvement remain unproven.",
        )
