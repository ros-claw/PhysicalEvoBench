import json

import pytest

from physicalevobench.v02.agent import AgentAdapter, Phase, SkillProgram
from physicalevobench.v02.gate import GateCriteria, decide


def make_pair(i, success=0, hard=False):
    sample = {'effective_success': 0., 'violation_rate': 0., 'violation_time_fraction': 0.,
              'depth_q95_fraction': 0., 'hard_event': False}
    return {'condition_id': str(i), 'baseline': dict(sample),
            'candidate': {**sample, 'effective_success': success, 'hard_event': hard}}


def test_small_identical_sample_is_inconclusive_not_proven_unsafe():
    assert decide([make_pair(i) for i in range(3)], GateCriteria(.05, .02))['decision'] == 'INCONCLUSIVE'


def test_absolute_event_and_unsafe_baseline_cannot_be_accepted():
    pair = make_pair(0, 1, True)
    assert decide([pair], GateCriteria(0., 1.))['reason'] == 'candidate_absolute_hard_event'
    pair['candidate']['hard_event'] = False
    pair['baseline']['hard_event'] = True
    assert decide([pair], GateCriteria(0., 1.))['reason'] == 'unsafe_baseline_requires_recalibration'


def test_gate_accepts_only_with_simultaneous_task_and_risk_evidence():
    pairs = [make_pair(i, 1) for i in range(3000)]
    assert decide(pairs, GateCriteria(.05, .1))['decision'] == 'ACCEPT'
    assert decide([make_pair(i) for i in range(3000)], GateCriteria(.1, .1))['decision'] == 'REJECT'
    with pytest.raises(ValueError, match='independent'):
        decide([pairs[0], pairs[0]], GateCriteria(.05, .1))


def test_program_reloads_in_fresh_session_and_failed_trials_keep_cost(tmp_path):
    def failed(program, handle):
        raise RuntimeError('native failure')

    adapter = AgentAdapter(lambda: {'joint_position': [0]*7}, failed, failed, 1, 0, tmp_path/'ledger')
    program = SkillProgram((Phase('close', 25, (0, -.5, 0, -2., 0, 2., .7), 'close'),))
    ref = adapter.propose(program.to_dict())
    assert adapter.propose(program.to_dict()) == ref
    with pytest.raises(RuntimeError, match='native failure'):
        adapter.run_trial(ref, 'public-train-000')
    assert adapter.remaining['trial'] == 0
    assert len((tmp_path/'ledger').read_text().splitlines()) == 1
    with pytest.raises(ValueError, match='budget'):
        adapter.run_trial(ref, 'public-train-000')
    artifact = tmp_path/'frozen.json'
    adapter.freeze(ref, artifact)
    fresh = AgentAdapter(lambda: {}, failed, failed, 0, 0, tmp_path/'fresh-ledger')
    new_ref = fresh.load(artifact)
    assert new_ref == ref
    assert fresh.programs[new_ref].action(0, .5, [0]*7) == program.action(0, .5, [0]*7)
    value = json.loads(artifact.read_text())
    value['program']['phases'][0]['arm_target_rad'][0] = .1
    artifact.write_text(json.dumps(value))
    another = AgentAdapter(lambda: {}, failed, failed, 0, 0, tmp_path/'another-ledger')
    with pytest.raises(ValueError, match='digest'):
        another.load(artifact)


def test_program_rejects_evaluator_code_or_physics_edits():
    with pytest.raises(ValueError):
        SkillProgram.from_dict({'schema': 'v02-joint-program-1', 'phases': [], 'gravity': 0})
    with pytest.raises(TypeError):
        Phase('close', 10, (0,)*7, 'close', python='import os')
