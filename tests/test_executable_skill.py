import copy

import pytest

from physicalevobench.core.expressions import comparison as cmp
from physicalevobench.core.program import Program, ProgramFSM
from physicalevobench.core.tasks import task
from physicalevobench.development.place import candidate


def observation():
    return {'ee_position': [.62, .12, .03], 'object_position': [.62, .12, .021],
            'goal_position': [.5, 0., .3], 'task_goal_position': [.62, .12, .021],
            'object_velocity': [0., 0., 0.], 'finger_position': [.024, .024],
            'cube_contact_force': [10., 10.], 'orientation_error': 0.}


def test_release_guard_requires_actual_opening_and_contact_loss():
    fsm = ProgramFSM(candidate('open'))
    fsm.current = 'release'
    obs = observation()
    for _ in range(100):
        assert fsm.update(obs, .02)['program_node'] == 'release'
    obs.update(finger_position=[.04, .04], cube_contact_force=[0., 0.])
    for _ in range(6):
        result = fsm.update(obs, .02)
    assert result['program_node'] == 'retreat'


def test_settle_guard_rejects_fast_crossing_and_resets_dwell():
    fsm = ProgramFSM(candidate('settle'))
    fsm.current = 'lower'
    obs = observation()
    obs['object_velocity'] = [0., .27, 0.]
    for _ in range(25):
        assert fsm.update(obs, .02)['program_node'] == 'lower'
    obs['object_velocity'] = [0., 0., 0.]
    for _ in range(3):
        assert fsm.update(obs, .02)['program_node'] == 'lower'
    fast = {**obs, 'object_velocity': [.2, 0., 0.]}
    fsm.update(fast, .02)
    assert fsm.dwell == 0
    for _ in range(6):
        result = fsm.update(obs, .02)
    assert result['program_node'] == 'release'


def test_goal_target_comes_from_public_goal_and_rejects_private_paths():
    program = candidate('settle_open')
    fsm = ProgramFSM(program)
    obs = observation()
    fsm.current = 'lower'
    a = fsm.update(obs, .02)['target_position']
    obs['task_goal_position'] = [.55, -.1, .021]
    b = fsm.update(obs, .02)['target_position']
    assert b[0]-a[0] == pytest.approx(-.07)
    assert b[1]-a[1] == pytest.approx(-.22)
    for guard in [cmp('object_mass_kg', 'ge', .1), {'eval': 'x'},
                  {'all': []}, cmp('object_speed', 'le', float('nan'))]:
        bad = copy.deepcopy(program.to_dict())
        bad['nodes'][0]['guard'] = guard
        with pytest.raises(ValueError):
            Program.from_dict(bad)


def test_task_lifecycle_does_not_block_other_task_development():
    assert task('lift-regression', 'DEV')['status'] == 'REGRESSION'
    assert task('place-settle', 'DEV')['status'] == 'DEV'
    with pytest.raises(ValueError, match='formal scores'):
        task('place-settle', 'BENCHMARK')
