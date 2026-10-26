import pytest

from physicalevobench.v02.metrics import train_recipe


@pytest.mark.parametrize('start,end,halve', [
    (100, 100, True), (100, 102, False), (-100, -100, True),
    (-100, -100.5, True), (-100, -98, False), (-1, 1, False),
    (0, 0, True), (0, .005, True), (0, .02, False),
])
def test_signed_train_feedback(start, end, halve):
    value = train_recipe([start]*4+[end]*4, 1e-4)
    assert value['halved'] is halve
    assert value['learning_rate'] == (5e-5 if halve else 1e-4)


def test_signed_recipe_rejects_invalid_scale_and_preserves_floor():
    with pytest.raises(ValueError):
        train_recipe([0], 1e-4, 0)
    assert train_recipe([-100]*4, 1e-5)['learning_rate'] == 1e-5


def test_physical_target_envelope_limits_arm_and_binary_finger_targets():
    from physicalevobench.v02.execution import TargetEnvelope

    layer = TargetEnvelope(['arm', 'finger'], [[-2, 2], [0, .04]], [2, .2], .02)
    layer.reset([0, .04])
    out = layer.apply([500, 0])
    assert out['applied_target'] == pytest.approx([.02, .0392])
    assert out['limited_joints'] == ['arm', 'finger']
    for _ in range(200):
        out = layer.apply([500, -.1])
    assert out['applied_target'] == [2, 0]


def test_envelope_reports_infeasible_initial_state_instead_of_claiming_rate_safety():
    from physicalevobench.v02.execution import TargetEnvelope

    layer = TargetEnvelope(['finger'], [[0, .04]], [.2], .02)
    layer.reset([-.02])
    out = layer.apply([0])
    assert out['initial_state_rate_conflicts'] == ['finger']
    assert out['applied_target'] == [0]
