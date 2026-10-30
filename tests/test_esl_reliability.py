"""CPU contracts and analytic fixtures; none are physical evidence."""

import concurrent.futures
import subprocess
import time
from pathlib import Path

import pytest


def test_concurrent_source_export_never_observes_half_written_module(tmp_path,monkeypatch):
    from physicalevobench.calibration.source_snapshot import snapshot_source

    package=tmp_path/'physicalevobench'
    package.mkdir()
    (package/'__init__.py').write_text('VALUE = 7\n'*100)
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()
    git('init','-q')
    git('add','.')
    git('-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','CPU fixture')
    ref=git('rev-parse','HEAD')
    write=Path.write_bytes
    def slow_write(path,data):
        if 'study-source' in str(path) and path.name=='__init__.py':
            with path.open('wb') as stream:
                stream.write(data[:1])
                stream.flush()
                time.sleep(.03)
                stream.write(data[1:])
            return len(data)
        return write(path,data)
    monkeypatch.setattr(Path,'write_bytes',slow_write)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        values=list(pool.map(lambda _:snapshot_source(tmp_path,ref),range(12)))
    assert all(v==values[0] for v in values)
    (values[0][0]/'physicalevobench/__init__.py').write_text('TAMPERED')
    with pytest.raises(ValueError,match='cache changed'):
        snapshot_source(tmp_path,ref)


def test_provider_service_failure_is_not_a_participant_graph_failure(tmp_path):
    import sys

    from physicalevobench.core.errors import ProviderAuthError,ProviderTransportError
    from physicalevobench.core.model import ParticipantProcess

    for code,error in [("import sys;sys.stderr.write('HTTP 401 unauthorized');sys.exit(1)",ProviderAuthError),
                       ("import sys;sys.stderr.write('service unavailable');sys.exit(1)",ProviderTransportError)]:
        p=ParticipantProcess([sys.executable,'-c',code],'CPU-fixture',tmp_path/error.__name__)
        with pytest.raises(error):
            p.call({'CPU_contract':True})
        assert p.calls==1
        import json
        budget=json.loads((p.log_dir/'budget.json').read_text())
        assert budget['input_tokens']=='unknown'
        assert not (p.log_dir/'call-00/usage.json').exists()


def test_usage_unknown_and_deadline_are_explicit_and_never_zero_filled(tmp_path,monkeypatch):
    import json
    import sys

    from physicalevobench.core.errors import ProviderDeadline,ProviderUsageUnknown
    from physicalevobench.core.model import ParticipantProcess

    p=ParticipantProcess([sys.executable,'-c',"print('{\"response\":{},\"usage\":{}}')"],
                         'CPU-fixture',tmp_path/'usage')
    with pytest.raises(ProviderUsageUnknown):
        p.call({})
    assert json.loads((p.log_dir/'budget.json').read_text())['output_tokens']=='unknown'
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired('CPU_fixture',120)
    monkeypatch.setattr(subprocess,'run',timeout)
    q=ParticipantProcess(['unused'],'CPU-fixture',tmp_path/'deadline')
    with pytest.raises(ProviderDeadline):
        q.call({})
    assert q.calls==1
    assert json.loads((q.log_dir/'call-00/process.json').read_text())['usage']=='unknown'


def test_notes_and_numeric_serialization_do_not_create_new_executable_behavior():
    from physicalevobench.core.artifact import executable_fingerprint
    from physicalevobench.development.place import starter_program

    a={'skill':starter_program().to_dict(),'memory':'first self-written note'}
    b={'skill':starter_program().to_dict(),'memory':'a completely different note'}
    b['skill']['nodes'][0]['minimum_s']=0
    assert executable_fingerprint(a)==executable_fingerprint(b)
    b['skill']['nodes'][0]['timeout_s']=19.
    assert executable_fingerprint(a)!=executable_fingerprint(b)


def test_ready_checks_physical_support_not_only_a_motionless_visual_pose():
    import copy

    from physicalevobench.core.readiness import decision

    frame={'object_position':[[.5,0.,.021]],'object_velocity':[[0.]*6],
           'object_orientation':[[1.,0.,0.,0.]],'joint_position':[[0.]*9],
           'joint_velocity':[[0.]*9],'mass':[[.1]],'inertia':[[1.]*9],
           'support':{'cube_net_normal_force_w':[[[0.,0.,.981]]]}}
    frames=[copy.deepcopy(frame) for _ in range(40)]
    assert decision(frames,.1,True)[0]
    assert not decision(frames,.1,False)[0]
    frames[-1]['object_position'][0][2]=-.02
    assert not decision(frames,.1,True)[0]
    frames[-1]=copy.deepcopy(frame)
    for f in frames:
        f['support']['cube_net_normal_force_w']=[[[0.,0.,0.]]]
    assert not decision(frames,.1,True)[0]


def test_state_executor_has_no_checkpoint_or_model_weight_identity():
    import json

    from physicalevobench.core.state_config import StateExecutionSkill,reference,worker_config

    base=reference({'reference_config':{}})
    cfg=worker_config(base,1)
    assert 'checkpoint_path' not in cfg and 'checkpoint_sha256' not in cfg
    skill=StateExecutionSkill(cfg['state_execution_sha256'])
    assert 'base_checkpoint_sha256' not in skill.to_dict()
    assert 'model_1999' not in json.dumps(cfg)
