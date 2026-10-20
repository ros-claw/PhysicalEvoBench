"""Explicit feedback allowlist. Physical truth and heldout results never enter proposals."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingFeedback:
    episode_id: str
    success: bool
    failure_type: str | None
    split: str = "train"

    def __post_init__(self):
        if self.split != "train":
            raise ValueError("Only train feedback may enter an evolution agent")
        if type(self.success) is not bool:
            raise ValueError("success must be a boolean")

    @classmethod
    def from_payload(cls, payload):
        # Reject unknown fields, rather than passing evaluator-only data through.
        return cls(**payload)
