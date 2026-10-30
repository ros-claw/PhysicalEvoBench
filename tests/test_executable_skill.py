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


def test_task_lifecycle_does_not_block_other_task_development(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert task('lift-regression', 'DEV')['status'] == 'REGRESSION'
    assert task('place-settle', 'DEV')['status'] == 'DEV'
    with pytest.raises(ValueError, match='formal scores'):
        task('place-settle', 'BENCHMARK')


def test_new_graph_cannot_select_hidden_fixed_place_geometry_or_nonfinite_goal():
    program = candidate('aperture').to_dict()
    program['nodes'][0]['target'] = 'place_lower'
    with pytest.raises(ValueError, match='public goal'):
        Program.from_dict(program)
    fsm = ProgramFSM(candidate('aperture'))
    obs = observation()
    obs['task_goal_position'][0] = float('nan')
    with pytest.raises(ValueError, match='public goal'):
        fsm.update(obs, .02)


def test_support_query_manifests_are_distinct_and_physically_related(tmp_path):
    from physicalevobench.core.learning import manifest
    groups = manifest(tmp_path, tmp_path, 2)
    seeds = [c['seed'] for g in groups for cs in g.values() for c in cs]
    assert len(set(seeds)) == len(seeds)
    for group in groups:
        assert {c['object_mass_kg'] for c in group['support']} == {c['object_mass_kg'] for c in group['query']}
        assert {tuple(c['public_goal']) for c in group['support']}.isdisjoint(
            {tuple(c['public_goal']) for c in group['query']})


def test_paired_initial_audit_catches_seed_equal_but_reset_different():
    from physicalevobench.core.learning_audit import assert_initial_pair
    a = {'joint_position': [[0., 0.]], 'object_position': [[.5, 0., .055]],
         'target_command': [[.6, .1, .2]]}
    b = copy.deepcopy(a)
    assert_initial_pair(a, b)
    b['joint_position'][0][1] = .001
    with pytest.raises(ValueError, match='initial physical'):
        assert_initial_pair(a, b)


def test_invalid_designer_is_retained_as_failure_without_any_physics(tmp_path):
    import json
    import sys

    from physicalevobench.core.learning import learn
    response = {'response': {'tool': 'freeze', 'program_json': '{}',
                             'practice_handle': '', 'memory': ''},
                'usage': {'input_tokens': 12, 'output_tokens': 3}}
    provider = [sys.executable, '-c', 'print('+repr(json.dumps(response))+')']
    group = {'support': []}
    result = learn(tmp_path, tmp_path, 'a'*40, {}, {}, group, 'designer', 'CPU-fixture',
                   provider, 'cpu-only-test', 2)
    assert result is None
    failure = json.loads((tmp_path/'designer/validity_failure.json').read_text())
    assert failure['status'] == 'INVALID_PARTICIPANT_SUBMISSION'
    assert 'denominator' in failure['query_scoring']
    assert not (tmp_path/'designer/native').exists()
    assert json.loads((tmp_path/'designer/model_calls/budget.json').read_text())['input_tokens'] == 120


def test_common_batch_search_uses_identical_conditions_before_selection(tmp_path, monkeypatch):
    from physicalevobench.core import learning
    from physicalevobench.development.place import conditions

    jobs = []

    class CPUOnlySession:
        def __init__(self, *args):
            pass

        def ready(self):
            pass

        def close(self):
            pass

        def trial(self, job):
            jobs.append(job)
            # Candidate 1 and 2 tie at 2/2, predeclared stable tie selects 1.
            candidate = int(job['episode_id'].split('-')[1])
            return {'success': candidate in (1, 2)}

    monkeypatch.setattr(learning, 'NativeSession', CPUOnlySession)
    base = {'reference_config': {}}
    group = {'support': conditions('CPU-only', 123, 4)}
    result = learning.score_search(tmp_path, tmp_path, 'a'*40, {}, base, group, 'cpu-only', 2)
    assert len(jobs) == 8
    for i in range(4):
        assert [j['condition'] for j in jobs[2*i:2*i+2]] == [j['condition'] for j in jobs[:2]]
    assert result['payload']['skill'] == learning.search_candidates()[1].to_dict()
    assert result['payload']['budget_used'] == 8


def test_learning_problem_qualification_binds_query_family_not_just_backend():
    from physicalevobench.core.problem import PROFILE, validate_problem
    from physicalevobench.v02.reference_artifact import digest
    q = {'status': 'QUALIFIED', 'learning_problem_sha256': digest(PROFILE)}
    validate_problem(PROFILE, q)
    old = copy.deepcopy(PROFILE)
    old['query_goal_positions'] = [[.58, .10, .021], [.64, -.08, .021]]
    with pytest.raises(ValueError, match='query distribution'):
        validate_problem(old, q)
    support = PROFILE['support_goal_positions']
    query = PROFILE['query_goal_positions']
    assert {p[0] for p in support} == {p[0] for p in query}
    assert {p[1] for p in support} == {p[1] for p in query}
    assert {tuple(p) for p in support}.isdisjoint({tuple(p) for p in query})


def test_pairing_rejects_different_inertia_velocity_or_nonfinite_measured_state():
    from physicalevobench.core.learning_audit import assert_initial_pair
    a = {'joint_position': [[0.]], 'object_position': [[.5, 0., .055]],
         'target_command': [[.6, .1, .2]], 'object_velocity': [[0., 0., 0.]],
         'inertia_readback': [[[.0000384, 0., 0.]]]}
    for field, replacement in [('object_velocity', [[.01, 0., 0.]]),
                                ('inertia_readback', [[[.0000768, 0., 0.]]]),
                                ('inertia_readback', [[[.0000385, 0., 0.]]]),
                                ('object_position', [[float('nan'), 0., .055]])]:
        b = {**a, field: replacement}
        with pytest.raises(ValueError, match='initial physical'):
            assert_initial_pair(a, b)
