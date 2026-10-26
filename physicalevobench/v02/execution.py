"""Physical position targets, not a blanket normalized-action clamp."""

import math


class TargetEnvelope:
    version = 'live-joint-target-envelope-v02'

    def __init__(self, names, limits, velocity_limits, dt, arm_rate=1.0, finger_rate=.04):
        if len(names) != len(limits) or len(names) != len(velocity_limits) or dt <= 0:
            raise ValueError('Named live joint bounds, velocity limits and dt required')
        self.names, self.limits, self.dt = names, limits, dt
        self.rates = []
        for name, bound, velocity in zip(names, limits, velocity_limits, strict=True):
            if not all(math.isfinite(v) for v in (*bound, velocity)) or bound[0] >= bound[1] or velocity <= 0:
                raise ValueError('Invalid physical joint limits')
            self.rates.append(min(velocity, finger_rate if 'finger' in name else arm_rate))
        if min(self.rates) <= 0:
            raise ValueError('Positive target rate required')
        self.previous = None

    def reset(self, position):
        if len(position) != len(self.names) or not all(math.isfinite(v) for v in position):
            raise ValueError('Finite initial joint state required')
        self.previous = list(position)

    def apply(self, targets):
        if self.previous is None or len(targets) != len(self.names) or not all(math.isfinite(v) for v in targets):
            raise ValueError('Reset and finite processed joint targets required')
        applied, conflicts = [], []
        for j, (target, (low, high), rate, previous) in enumerate(zip(
                targets, self.limits, self.rates, self.previous, strict=True)):
            lo, hi = max(low, previous-rate*self.dt), min(high, previous+rate*self.dt)
            if lo > hi:
                # Starting outside the workspace can make both requirements infeasible.
                # Position takes precedence, and this conflict remains observable.
                applied.append(max(low, min(high, previous)))
                conflicts.append(self.names[j])
            else:
                applied.append(max(lo, min(hi, target)))
        self.previous = applied
        return {'processed_target': list(targets), 'applied_target': applied,
                'limited_joints': [self.names[j] for j, (a, b) in enumerate(zip(targets, applied, strict=True)) if a != b],
                'initial_state_rate_conflicts': conflicts,
                'scope': 'target position/rate bounds; actual joint state and solver effort remain separately measured'}
