"""Immutable skill snapshots; no dependence on hidden task parameters."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SkillSpec:
    base_checkpoint_sha256: str
    skill_version: int = 0
    arm_action_gain: float = 1.0

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{64}", self.base_checkpoint_sha256):
            raise ValueError("Expected verified lowercase SHA256 for base checkpoint")
        if type(self.skill_version) is not int or self.skill_version < 0:
            raise ValueError("skill_version must be a non-negative integer")
        if (type(self.arm_action_gain) not in (float, int)
                or not math.isfinite(self.arm_action_gain)
                or not 0.85 <= self.arm_action_gain <= 1.15):
            raise ValueError("arm_action_gain must be finite and within [0.85, 1.15]")
        object.__setattr__(self, "arm_action_gain", float(self.arm_action_gain))

    def to_dict(self):
        return {"schema_version": "0.1", **asdict(self)}

    @property
    def sha256(self):
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode()).hexdigest()

    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        if data.pop("schema_version", None) != "0.1":
            raise ValueError("Unsupported skill schema")
        return cls(**data)
