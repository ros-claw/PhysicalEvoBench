"""CPU methodology fixtures; none of these are physical episode evidence."""

import pytest

from physicalevobench.stability.audit import world_goal
from physicalevobench.stability.metrics import holding_metrics, paired_interval, train_recipe


def sample(within=True, velocity=0.):
    return {'object_position': [[0., 0., 0. if within else .1]],
            'goal_position_world': [[0., 0., 0.]], 'object_velocity': [[velocity, 0., 0., 0., 0., 0.]],
            'instant_predicate': within, 'step_dt': .02}


def test_hold_requires_sixteen_samples_and_cannot_bridge_failure():
    assert not holding_metrics([sample() for _ in range(15)])['stable_success']
    assert holding_metrics([sample() for _ in range(16)])['stable_success']
    broken = [sample() for _ in range(10)] + [sample(False)] + [sample() for _ in range(10)]
    assert not holding_metrics(broken)['stable_success']
    assert holding_metrics([sample(velocity=.201) for _ in range(100)])['instant_success']
    assert not holding_metrics([sample(velocity=.201) for _ in range(100)])['stable_success']


def test_pinned_predicate_and_nonfinite_state_are_checked():
    bad = sample()
    bad['instant_predicate'] = False
    with pytest.raises(ValueError, match='predicate'):
        holding_metrics([bad])
    bad = sample(velocity=float('nan'))
    with pytest.raises(ValueError, match='Nonfinite'):
        holding_metrics([bad])


def test_independent_world_transform_rotates_then_translates():
    assert world_goal([1., 2., 3.], [0., 0., 0., 1.], [.5, .2, .1]) == pytest.approx([.5, 1.8, 3.1])


def test_scheduler_only_train_rewards_and_bounded_rate():
    assert train_recipe([1.]*100, .0001)['learning_rate'] == .00005
    assert train_recipe([1.]*25+[2.]*75, .0001)['learning_rate'] == .0001
    assert train_recipe([1.]*100, .00001)['learning_rate'] == .00001
    with pytest.raises(ValueError):
        train_recipe([float('nan')], .0001)


def test_seed_stratification_preserves_negative_seed_and_labels_scope():
    result = paired_interval([[1]*10, [1]*10, [-1]*10], draws=1000)
    assert result['difference'] == pytest.approx(1/3)
    assert result['per_seed_difference'] == [1., 1., -1.]
    assert result['interval'] == pytest.approx([1/3, 1/3])
    assert 'not a population' in result['scope']
