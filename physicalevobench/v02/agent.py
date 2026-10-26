"""Narrow artifact/API foundation. This module is not an autonomous Agent.

The evaluator supplies opaque public-condition handles and sanitized feedback.
No Python source, evaluator config, mass, seeds or final scores are tool inputs.
Python callbacks are trusted evaluator code, not an untrusted-code sandbox.
Physical use and parameter-effect validation remain gated on W3 calibration.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Phase:
    name: str
    steps: int
    arm_target_rad: tuple
    gripper: str

    def __post_init__(self):
        if self.name not in ('approach', 'align', 'close', 'wait', 'lift', 'hold', 'recover'):
            raise ValueError('Unrecognized phase')
        if type(self.steps) is not int or not 1 <= self.steps <= 250:
            raise ValueError('Phase duration must be 1..250 controls')
        if len(self.arm_target_rad) != 7 or any(type(v) not in (int, float) or not math.isfinite(v)
                                              or abs(v) > 3.2 for v in self.arm_target_rad):
            raise ValueError('Seven finite joint position targets required')
        if self.gripper not in ('open', 'close'):
            raise ValueError('Binary gripper command required')
        object.__setattr__(self, 'arm_target_rad', tuple(float(v) for v in self.arm_target_rad))


@dataclass(frozen=True)
class SkillProgram:
    phases: tuple

    def __post_init__(self):
        if (not self.phases or len(self.phases) > 16 or any(type(p) is not Phase for p in self.phases)
                or sum(p.steps for p in self.phases) > 250):
            raise ValueError('Whitelisted finite program with <=250 controls required')
        object.__setattr__(self, 'phases', tuple(self.phases))

    def to_dict(self):
        return {'schema': 'v02-joint-program-1', 'phases': [asdict(p) for p in self.phases]}

    @classmethod
    def from_dict(cls, value):
        if set(value) != {'schema', 'phases'} or value['schema'] != 'v02-joint-program-1':
            raise ValueError('Unknown program schema or evaluator modification')
        return cls(tuple(Phase(**p) for p in value['phases']))

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'),
                                         allow_nan=False).encode()).hexdigest()

    def action(self, step, arm_scale, arm_offset):
        """Convert physical targets using trusted live action mapping.

        Phase names describe intended sequence only; there is no claim of
        Cartesian reach/grasp competence. The common TargetEnvelope executes
        position/rate limits and actual physical state is measured separately.
        """
        if type(step) is not int or step < 0 or not math.isfinite(arm_scale) or arm_scale == 0:
            raise ValueError('Nonnegative control index and nonzero live scale required')
        remaining = step
        phase = self.phases[-1]
        for item in self.phases:
            if remaining < item.steps:
                phase = item
                break
            remaining -= item.steps
        return [(v-offset)/arm_scale for v, offset in zip(phase.arm_target_rad, arm_offset, strict=True)] + [
            1. if phase.gripper == 'open' else -1.]


class AgentAdapter:
    """Evaluator-owned tools. The model/tool caller itself is external to this API."""

    def __init__(self, observe, trial, validate, trial_budget, validation_budget, ledger_path):
        if any(type(n) is not int or n < 0 for n in (trial_budget, validation_budget)):
            raise ValueError('Explicit nonnegative interaction budgets required')
        self._observe, self._trial, self._validate = observe, trial, validate
        self.remaining = {'trial': trial_budget, 'validate': validation_budget}
        self.ledger_path = Path(ledger_path)
        if self.ledger_path.exists():
            raise ValueError('Use a new evaluator session ledger')
        self.programs, self.frozen = {}, None

    def observe(self):
        return self._observe()

    def propose(self, payload):
        if self.frozen:
            raise ValueError('Session already frozen')
        program = SkillProgram.from_dict(payload)
        self.programs[program.sha256] = program
        return program.sha256

    def _run(self, kind, reference, handle):
        if self.frozen or reference not in self.programs or self.remaining[kind] <= 0:
            raise ValueError('Frozen, unknown candidate or exhausted tool budget')
        if not isinstance(handle, str) or not handle:
            raise ValueError('Opaque public condition handle required')
        # Persist the cost before callback. Failed trials also consume budget.
        reservation = {'tool': kind, 'program_sha256': reference, 'condition_handle': handle}
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open('a') as stream:
            stream.write(json.dumps(reservation, sort_keys=True)+'\n')
            stream.flush()
        self.remaining[kind] -= 1
        callback = self._trial if kind == 'trial' else self._validate
        return callback(self.programs[reference], handle)

    def run_trial(self, candidate_ref, training_condition_handle):
        return self._run('trial', candidate_ref, training_condition_handle)

    def validate(self, candidate_ref, validation_condition_handle):
        return self._run('validate', candidate_ref, validation_condition_handle)

    def freeze(self, reference, destination):
        if self.frozen or reference not in self.programs:
            raise ValueError('Unknown candidate or session already frozen')
        path = Path(destination)
        with path.open('x') as stream:
            json.dump({'program': self.programs[reference].to_dict(), 'sha256': reference}, stream,
                      sort_keys=True, allow_nan=False)
        self.frozen = reference
        return reference

    def load(self, artifact):
        """A fresh instance can reload only the frozen executable artifact."""
        value = json.loads(Path(artifact).read_text())
        reference = self.propose(value['program'])
        if reference != value['sha256']:
            del self.programs[reference]
            raise ValueError('Frozen artifact digest mismatch')
        return reference
