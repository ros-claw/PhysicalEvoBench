"""Proprioceptive finger-limit guard on an independently reset temporal controller."""

import math
from dataclasses import asdict, dataclass

from physicalevobench.protocols.temporal_skill import TemporalController, TemporalSkill


@dataclass(frozen=True)
class GuardedSkill(TemporalSkill):
    finger_guard_enabled: bool = False
    finger_margin_m: float = .002
    finger_lookahead_steps: int = 1

    def __post_init__(self):
        super().__post_init__()
        if type(self.finger_guard_enabled) is not bool:
            raise ValueError('Finger guard flag must be boolean')
        if (type(self.finger_margin_m) not in (int, float) or not math.isfinite(self.finger_margin_m)
                or not 0 <= self.finger_margin_m <= .01):
            raise ValueError('Finger guard margin must be in [0, .01] metres')
        if type(self.finger_lookahead_steps) is not int or not 0 <= self.finger_lookahead_steps <= 2:
            raise ValueError('Finger lookahead must be 0, 1 or 2 steps')
        object.__setattr__(self, 'finger_margin_m', float(self.finger_margin_m))

    def to_dict(self):
        return {'schema_version':'guarded-1', **asdict(self)}

    @classmethod
    def from_dict(cls,payload):
        data=dict(payload)
        if data.pop('schema_version',None)!='guarded-1':
            raise ValueError('Unsupported guarded skill')
        return cls(**data)

    def make_controller(self,mapping):
        return GuardedController(self,mapping)


class GuardedController:
    uses_proprioception = True

    def __init__(self,skill,mapping):
        self.skill=skill
        self.temporal=TemporalController(skill,mapping)
        self.gripper=mapping['gripper_action']['start']

    def apply(self,raw,step,proprioception):
        action=self.temporal.apply(raw,step)
        if self.skill.finger_guard_enabled and action[self.gripper]<0:
            if set(proprioception)!={'finger_position','finger_velocity','finger_lower_limits','step_dt'}:
                raise ValueError('Unexpected proprioception fields')
            if not all(len(proprioception[key])==2 for key in
                       ('finger_position','finger_velocity','finger_lower_limits')):
                raise ValueError('Expected two named finger joints')
            horizon=self.skill.finger_lookahead_steps*proprioception['step_dt']
            for q,v,low in zip(proprioception['finger_position'],proprioception['finger_velocity'],
                               proprioception['finger_lower_limits'],strict=True):
                if not all(math.isfinite(x) for x in (q,v,low,horizon)):
                    raise ValueError('Nonfinite proprioception')
                if min(q,q+horizon*v)<low+self.skill.finger_margin_m:
                    action[self.gripper]=1.
                    break
        return action
