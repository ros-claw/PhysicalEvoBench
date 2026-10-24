"""Predeclared finite-horizon holding and paired uncertainty calculations."""

import math
import random


def holding_metrics(samples):
    if not samples:
        raise ValueError('No physical samples')
    longest = current = 0
    instant = 0
    dt = samples[0]['step_dt']
    for sample in samples:
        if sample['step_dt'] != dt or dt <= 0:
            raise ValueError('Invalid sampling interval')
        pos, goal = sample['object_position'][0], sample['goal_position_world'][0]
        vel = sample['object_velocity'][0][:3]
        if not all(math.isfinite(v) for v in (*pos, *goal, *vel)):
            raise ValueError('Nonfinite holding state')
        within = math.dist(pos, goal) < .05
        if within != sample['instant_predicate']:
            raise ValueError('Pinned upstream predicate differs from reconstructed goal distance')
        instant += within
        qualifies = within and math.sqrt(sum(v*v for v in vel)) <= .2
        current = current + 1 if qualifies else 0
        longest = max(longest, current)
    duration = max(0, longest-1)*dt
    return {'stable_success': duration >= .3-1e-12, 'instant_success': instant > 0,
            'maximum_holding_span_s': duration, 'qualifying_samples_longest': longest,
            'instant_samples': instant, 'samples': len(samples), 'step_dt': dt,
            'position_tolerance_m': .05, 'maximum_speed_m_s': .2, 'required_span_s': .3,
            'scope': 'sampled goal occupancy and speed; no contact or between-sample claim'}


def paired_interval(groups, draws=10000, alpha=.05):
    """Stratified condition bootstrap, conditional on these learned trajectories."""
    if not groups or any(not g for g in groups):
        raise ValueError('Empty seed stratum')
    rng = random.Random(20261024)
    means = [sum(g)/len(g) for g in groups]
    boot = sorted(sum(sum(rng.choices(g, k=len(g)))/len(g) for g in groups)/len(groups)
                  for _ in range(draws))
    return {'difference': sum(means)/len(means), 'per_seed_difference': means,
            'interval': [boot[int(draws*alpha/2)], boot[min(draws-1, int(draws*(1-alpha/2)))]],
            'alpha': alpha, 'learning_seeds': len(groups), 'conditions': sum(map(len, groups)),
            'scope': 'condition resampling within fixed learning seeds; not a population-of-learners interval'}


def train_recipe(rewards, previous_rate):
    """Train-only bounded scheduler, with no validation or test input."""
    if not rewards or not all(math.isfinite(v) for v in rewards):
        raise ValueError('Need finite public training rewards')
    n = max(1, len(rewards)//4)
    start, end = sum(rewards[:n])/n, sum(rewards[-n:])/n
    rate = max(1e-5, previous_rate * (.5 if end <= start*1.01 else 1.))
    return {'learning_rate': rate, 'first_quartile_reward': start,
            'last_quartile_reward': end, 'rule': 'halve on <=1% reward growth; floor 1e-5'}


def promote(incumbent, candidate):
    def totals(rows):
        return (sum(r['success'] for r in rows), sum(r['stability']['instant_success'] for r in rows),
                sum(r['joint_limit_violation_count'] for r in rows),
                sum(r['safety']['joint_samples'] for r in rows))
    old, new = totals(incumbent), totals(candidate)
    depth_ok = all(max(r['safety']['per_joint'][j]['maximum_depth'] for r in candidate) <=
                   max(r['safety']['per_joint'][j]['maximum_depth'] for r in incumbent) +
                   (.002 if 'finger' in incumbent[0]['safety']['per_joint'][j]['joint'] else .01)
                   for j in range(len(incumbent[0]['safety']['per_joint'])))
    return {'promote': new[0] > old[0] and new[1] >= old[1] and new[2] <= old[2]
            and new[2]/new[3] <= old[2]/old[3] and depth_ok,
            'incumbent': old, 'candidate': new, 'per_joint_depth_guard': depth_ok}
