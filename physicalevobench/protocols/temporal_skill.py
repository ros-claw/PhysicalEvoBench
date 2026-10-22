"""Temporal controller snapshots, separate from immutable historical v0.1 skills."""

import hashlib
import json
import math
from dataclasses import asdict, dataclass

from physicalevobench.protocols.skill import SkillSpec


@dataclass(frozen=True)
class TemporalSkill:
    base_checkpoint_sha256: str
    skill_version: int = 0
    arm_action_gain: float = 1.0
    arm_smoothing_alpha: float = 1.0
    gripper_hold_steps: int = 0

    def __post_init__(self):
        SkillSpec(self.base_checkpoint_sha256, self.skill_version, self.arm_action_gain)
        if (type(self.arm_smoothing_alpha) not in (int, float)
                or not math.isfinite(self.arm_smoothing_alpha)
                or not .1 <= self.arm_smoothing_alpha <= 1.):
            raise ValueError('Arm smoothing alpha must be finite in [.1, 1]')
        if type(self.gripper_hold_steps) is not int or not 0 <= self.gripper_hold_steps <= 250:
            raise ValueError('Gripper hold must be integer steps in [0, 250]')
        object.__setattr__(self, 'arm_action_gain', float(self.arm_action_gain))
        object.__setattr__(self, 'arm_smoothing_alpha', float(self.arm_smoothing_alpha))

    def to_dict(self):
        return {'schema_version': 'temporal-1', **asdict(self)}

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        if data.pop('schema_version', None) != 'temporal-1':
            raise ValueError('Unsupported temporal skill')
        return cls(**data)

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'),
                                         allow_nan=False).encode()).hexdigest()

    def make_controller(self, mapping):
        return TemporalController(self, mapping)


class TemporalController:
    """Only policy commands and time enter the wrapper; no object mass or test labels."""

    def __init__(self, skill, mapping):
        self.skill = skill
        self.arm = range(mapping['arm_action']['start'], mapping['arm_action']['stop'])
        grip = mapping['gripper_action']
        if grip['stop'] - grip['start'] != 1 or grip['term_class'] != 'BinaryJointPositionAction':
            raise ValueError('Temporal hold requires verified signed binary gripper action')
        self.gripper = grip['start']
        self.previous = None
        self.open_seen = False
        self.remaining = 0

    def apply(self, raw, step):
        action = list(raw)
        for i in self.arm:
            proposed = raw[i] * self.skill.arm_action_gain
            action[i] = proposed if self.previous is None else (
                self.skill.arm_smoothing_alpha * proposed
                + (1 - self.skill.arm_smoothing_alpha) * self.previous[i])
        if self.skill.gripper_hold_steps:
            if self.remaining:
                action[self.gripper] = -1.
                self.remaining -= 1
            elif raw[self.gripper] > 0:
                self.open_seen = True
            elif raw[self.gripper] < 0 and self.open_seen and step >= 15:
                action[self.gripper] = -1.
                self.remaining = self.skill.gripper_hold_steps - 1
                self.open_seen = False
        # Match stored float32 applied actions, including the filter's persistent memory.
        import struct

        action = [struct.unpack('f', struct.pack('f', x))[0] for x in action]
        self.previous = action
        return action
