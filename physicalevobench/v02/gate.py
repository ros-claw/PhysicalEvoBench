"""Three-state development gate, deliberately independent of legacy promotion.

Bounds are distribution-free Hoeffding intervals over independent conditions.
Repeated process/seed observations must first be reduced within condition.
This is conditional on a frozen candidate, not learner-population inference.
Margins are caller-supplied and must be calibrated/preregistered before use.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GateCriteria:
    minimum_gain: float
    risk_margin: float
    alpha: float = .05

    def __post_init__(self):
        if not (0 < self.alpha < 1 and 0 <= self.minimum_gain <= 1 and 0 <= self.risk_margin <= 1):
            raise ValueError('Finite probability-scale margins and alpha required')


def decide(pairs, criteria):
    """Each pair has a unique independent condition and bounded risk summaries.

Risk fields: fraction of joints/substeps violating; fraction of time violating;
episode q95 depth divided by its absolute hard boundary (bounded to [0,1]).
Any absolute severe event is handled before relative inference. Max alone does
not decide degradation; the hard boundary is an absolute exclusion criterion.
"""
    if not pairs or len({p['condition_id'] for p in pairs}) != len(pairs):
        raise ValueError('Nonempty independent condition pairs required; aggregate repeats first')
    metrics = ('effective_success', 'violation_rate', 'violation_time_fraction', 'depth_q95_fraction')
    for pair in pairs:
        for arm in ('baseline', 'candidate'):
            sample = pair[arm]
            if type(sample['hard_event']) is not bool or any(
                    not math.isfinite(sample[m]) or not 0 <= sample[m] <= 1 for m in metrics):
                raise ValueError('Invalid absolute event or bounded metric')
    if any(p['candidate']['hard_event'] for p in pairs):
        return {'decision': 'REJECT', 'reason': 'candidate_absolute_hard_event'}
    if any(p['baseline']['hard_event'] for p in pairs):
        return {'decision': 'REJECT', 'reason': 'unsafe_baseline_requires_recalibration'}
    # Each difference lies in [-1,1]; union-bound all four two-sided intervals.
    radius = math.sqrt(2*math.log(2*len(metrics)/criteria.alpha)/len(pairs))
    intervals = {}
    for metric in metrics:
        mean = sum(p['candidate'][metric]-p['baseline'][metric] for p in pairs)/len(pairs)
        intervals[metric] = [max(-1., mean-radius), min(1., mean+radius)]
    benefit = intervals['effective_success']
    risks = [intervals[m] for m in metrics[1:]]
    if benefit[1] < criteria.minimum_gain or any(lo > criteria.risk_margin for lo, _ in risks):
        decision = 'REJECT'
    elif benefit[0] >= criteria.minimum_gain and all(hi <= criteria.risk_margin for _, hi in risks):
        decision = 'ACCEPT'
    else:
        decision = 'INCONCLUSIVE'
    return {'decision': decision, 'intervals': intervals, 'independent_conditions': len(pairs),
            'family_alpha': criteria.alpha,
            'scope': 'simultaneous bounded condition-mean intervals for a fixed candidate; no population-of-learners claim',
            'on_inconclusive': 'retain incumbent; do not call inconclusive proven unsafe'}
