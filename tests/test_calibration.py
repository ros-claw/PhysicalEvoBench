from physicalevobench.calibration.safety import summarize_safety


def test_coordinate_safety_exposure_and_depth():
    result = summarize_safety([[0., -.002], [1.01, 0.]], [[0., 1.], [0., .04]],
                              ['panda_joint1', 'panda_finger_joint1'], .02)
    assert result['violation_joint_samples'] == 2
    assert result['violations_per_1000_joint_samples'] == 500
    assert result['per_joint'][0]['maximum_depth'] > .0099
    assert result['per_joint'][1]['unit'] == 'm'
    assert result['per_joint'][1]['duration_over_tolerance_s'] == .02
    assert result['collision'] == 'NOT_MEASURED'


def test_training_schema_rejects_hidden_truth():
    import pytest
    from physicalevobench.calibration.public_schema import learner_feedback

    public = {'observations':{'policy':[], 'task_obs':[]}, 'rewards':[], 'dones':[], 'time_outs':[]}
    assert learner_feedback(public) is public
    for key in ('mass', 'seed', 'heldout_results', 'environment'):
        with pytest.raises(ValueError):
            learner_feedback({**public,key:123})
    with pytest.raises(ValueError):
        learner_feedback({**public,'observations':{'policy':[], 'task_obs':[], 'mass':[]}})


def test_exact_power_all_discordances_favor_update():
    import math
    from physicalevobench.calibration.power import paired_power

    # At one-sided alpha=.05, at least five wins with no losses are needed.
    expected=1-sum(math.comb(32,k)*.2**k*.8**(32-k) for k in range(5))
    assert abs(paired_power(32,.2,.2)-expected)<1e-12
    assert paired_power(32,0,.3)<=.05
