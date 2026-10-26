"""v0.2 train-only recipe: signed rewards and explicit scale around zero."""

import math


def train_recipe(rewards, previous_rate, reward_scale_floor=1.0):
    if (not rewards or not all(math.isfinite(x) for x in rewards)
            or not math.isfinite(previous_rate) or previous_rate <= 0
            or not math.isfinite(reward_scale_floor) or reward_scale_floor <= 0):
        raise ValueError('Finite rewards, positive rate and positive scale floor required')
    n = max(1, len(rewards)//4)
    start, end = sum(rewards[:n])/n, sum(rewards[-n:])/n
    gain = (end-start)/max(abs(start), reward_scale_floor)
    halve = gain <= .01
    return {'schema': 'signed-reward-recipe-v02',
            'learning_rate': max(1e-5, previous_rate*(.5 if halve else 1.)),
            'first_quartile_reward': start, 'last_quartile_reward': end,
            'relative_gain': gain, 'reward_scale_floor': reward_scale_floor,
            'halved': halve, 'rule': 'signed delta / max(abs(start), scale floor) <= 0.01'}
