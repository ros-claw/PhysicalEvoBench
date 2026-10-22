import pytest

from physicalevobench.protocols.temporal_skill import TemporalSkill

MAPPING = {'arm_action': {'start': 0, 'stop': 2},
           'gripper_action': {'start': 2, 'stop': 3, 'term_class': 'BinaryJointPositionAction'}}


def test_identity_and_smoothing_reset():
    skill = TemporalSkill('a'*64)
    c = skill.make_controller(MAPPING)
    assert c.apply([2., -3., 20.], 0) == [2., -3., 20.]
    assert c.apply([4., 7., -20.], 1) == [4., 7., -20.]
    smooth = TemporalSkill('a'*64, arm_smoothing_alpha=.5)
    c = smooth.make_controller(MAPPING)
    assert c.apply([2., 0., 10.], 0) == [2., 0., 10.]
    assert c.apply([4., 2., -10.], 1) == [3., 1., -10.]
    assert smooth.make_controller(MAPPING).apply([4., 2., -10.], 0) == [4., 2., -10.]


def test_gripper_hold_exact_duration_and_no_initial_latch():
    skill = TemporalSkill('a'*64, gripper_hold_steps=3)
    c = skill.make_controller(MAPPING)
    assert c.apply([0., 0., -7.], 0)[2] == -7.
    assert c.apply([0., 0., 10.], 14)[2] == 10.
    assert c.apply([0., 0., -7.], 15)[2] == -1.
    assert c.apply([0., 0., 20.], 16)[2] == -1.
    assert c.apply([0., 0., 20.], 17)[2] == -1.
    assert c.apply([0., 0., 20.], 18)[2] == 20.
    assert c.apply([0., 0., -2.], 19)[2] == -1.


def test_temporal_hashes_and_bounds():
    skill = TemporalSkill('a'*64, gripper_hold_steps=50)
    assert TemporalSkill.from_dict(skill.to_dict()) == skill
    assert skill.sha256 != TemporalSkill('a'*64).sha256
    for value in [True, -1, 251, 1.5]:
        with pytest.raises(ValueError):
            TemporalSkill('a'*64, gripper_hold_steps=value)
    for value in [float('nan'), 0, 1.1, True]:
        with pytest.raises(ValueError):
            TemporalSkill('a'*64, arm_smoothing_alpha=value)


def test_predictive_finger_guard_and_disabled_identity():
    from physicalevobench.protocols.guarded_skill import GuardedSkill

    state={'finger_position':[.02,.02], 'finger_velocity':[0.,0.],
           'finger_lower_limits':[0.,0.], 'step_dt':.02}
    disabled=GuardedSkill('a'*64).make_controller(MAPPING)
    assert disabled.apply([0.,0.,-20.],0,state)[2]==-20.
    enabled=GuardedSkill('a'*64,finger_guard_enabled=True).make_controller(MAPPING)
    assert enabled.apply([0.,0.,-20.],0,state)[2]==-20.
    state['finger_position']=[.003,.02]
    state['finger_velocity']=[-.2,0.]
    assert enabled.apply([0.,0.,-20.],1,state)[2]==1.
    assert enabled.apply([0.,0.,20.],2,state)[2]==20.
    with pytest.raises(ValueError):
        GuardedSkill('a'*64,finger_lookahead_steps=True)
