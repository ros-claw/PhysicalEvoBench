import json
import tarfile
from pathlib import Path

import pytest
import yaml

from physicalevobench.agents.guarded_search_worker import respond
from physicalevobench.protocols.guarded_skill import GuardedSkill
from scripts.run_confirmation import prepare


def history_entry(successes,version=0,**params):
    return {'skill':GuardedSkill('a'*64,skill_version=version,**params).to_dict(),
            'feedback':[{'episode_id':f'train-{version}-{i}','success':i<successes,
                         'failure_type':None if i<successes else 'task_not_completed','split':'train'}
                        for i in range(8)]}


def test_guarded_proposal_changes_with_train_feedback_but_random_does_not():
    history=[history_entry(1),history_entry(4,1,finger_guard_enabled=True),
             history_entry(2,2,finger_guard_enabled=True)]
    request={'agent':'feedback','rng_seed':12,'history':history,'remaining_budget':8}
    assert respond(request)['candidate_name']=='hold10guard2'
    request['agent']='random'
    before=respond(request)['candidate_name']
    history[1]=history_entry(0,1,finger_guard_enabled=True)
    assert respond(request)['candidate_name']==before
    request['agent']='feedback'
    assert respond(request)['candidate_name']=='guard6look2'
    history[0]['feedback'][0]['mass']=2.3
    with pytest.raises(TypeError):
        respond(request)


def test_failed_real_development_gate_blocks_formal_physics(tmp_path):
    root=Path(__file__).resolve().parents[1]
    archive=root/'docs/evidence/guarded-development-20261022-001/validation.tar.gz'
    gate=tmp_path/'gate'
    gate.mkdir()
    with tarfile.open(archive,'r:gz') as tar:
        for name in ('decision.json','audit.json'):
            (gate/name).write_bytes(tar.extractfile('validation/'+name).read())
    assert json.loads((gate/'decision.json').read_text())['decision']=='rollback'
    config=yaml.safe_load((root/'configs/guarded_confirmation.yaml').read_text())
    output=tmp_path/'forbidden-test'
    with pytest.raises(ValueError,match='did not promote'):
        prepare(config,output,[0,1,2],gate)
    assert not output.exists()
