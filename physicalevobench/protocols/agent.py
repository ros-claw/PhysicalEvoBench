"""The updater contract contains no simulator objects or heldout conditions."""

from dataclasses import dataclass
from typing import Protocol

from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec


@dataclass(frozen=True)
class SkillProposal:
    skill: SkillSpec
    source_episode_ids: tuple[str, ...]
    hypothesis: str


class EvolutionAgent(Protocol):
    def propose_update(
        self, current_skill: SkillSpec, training_feedback: list[TrainingFeedback],
        remaining_budget: int,
    ) -> SkillProposal | None: ...
