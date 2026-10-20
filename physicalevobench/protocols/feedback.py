"""Explicit feedback allowlist. Physical truth and heldout results never enter proposals."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingFeedback:
    episode_id: str
    success: bool
    failure_type: str | None
    split: str = "train"

    def __post_init__(self):
        if not isinstance(self.episode_id, str) or not 1 <= len(self.episode_id) <= 128:
            raise ValueError("episode_id must be a nonempty string of at most 128 characters")
        if self.split != "train":
            raise ValueError("Only train feedback may enter an evolution agent")
        if type(self.success) is not bool:
            raise ValueError("success must be a boolean")
        if self.failure_type is not None and (
            not isinstance(self.failure_type, str) or self.failure_type not in
            {"failed_to_lift", "task_not_completed", "object_dropped", "timeout"}
        ):
            raise ValueError("Unknown failure label; nested evaluator data is forbidden")
        if self.success and self.failure_type is not None:
            raise ValueError("A successful episode cannot have a failure label")

    @classmethod
    def from_payload(cls, payload):
        # Reject unknown fields, rather than passing evaluator-only data through.
        return cls(**payload)
