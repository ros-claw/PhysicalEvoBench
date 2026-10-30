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


def test_block_statistics_keep_missingness_and_identity_discordance():
    from physicalevobench.core.replication_metrics import ARMS,comparison,summarize

    cs=[{'condition_id':str(i),'public_goal':[.6,.12,.021],'object_mass_kg':.1} for i in range(4)]
    scores={a:{str(i):i%2==0 for i in range(4)} for a in ARMS}
    scores['deletion']={str(i):i%2==1 for i in range(4)}
    block={'block':0,'conditions':cs,'scores':scores}
    result=summarize([block])
    assert result['identity_replays'][0]['discordant_pairs']==4
    assert result['comparisons']['designer']['hierarchical_95_interval'] is None
    second={'block':1,'conditions':cs,'scores':{a:dict(v) for a,v in scores.items()}}
    assert comparison([block,second],'designer',draws=100)['hierarchical_95_interval']==[0.,0.]
    second['scores']['feedback']['0']=None
    assert comparison([block,second],'designer',draws=100)['hierarchical_95_interval'] is None
    assert summarize([second])['arms']['feedback']['missing']==1


def test_v3_handle_current_program_memory_invalid_repair_and_submission_order(tmp_path,monkeypatch):
    import json

    import physicalevobench.core.learning as learning
    from physicalevobench.core.state_config import reference
    from physicalevobench.development.place import starter_program

    base=reference({'reference_config':{}})
    program=starter_program().to_dict()
    program['nodes'][0]['timeout_s']=1.7
    replies=[{'tool':'revise','program_json':json.dumps(program),'practice_handle':'','memory':'my note'},
             {'tool':'run_trial','program_json':'broken','practice_handle':'practice-0','memory':'invalid note'},
             {'tool':'run_trial','program_json':json.dumps(program),'practice_handle':'practice-1','memory':'first trial'},
             {'tool':'run_trial','program_json':json.dumps(program),'practice_handle':'practice-0','memory':'second trial'},
             {'tool':'freeze','program_json':json.dumps(program),'practice_handle':'','memory':'final note'}]
    requests,jobs=[],[]
    class Model:
        input_tokens=output_tokens=0
        calls=0
        def __init__(self,*args,**kwargs):
            pass
        def call(self,request):
            requests.append(request)
            return replies[len(requests)-1]
    class Session:
        def __init__(self,root,out,*args):
            self.out=out
        def ready(self):
            pass
        def trial(self,job):
            jobs.append(job)
            return {'success':False,'execution_status':'OK'}
        def close(self):
            pass
    monkeypatch.setattr(learning,'ParticipantProcess',Model)
    monkeypatch.setattr(learning,'NativeSession',Session)
    monkeypatch.setattr(learning,'event_feedback',lambda directory,row:{'success':False,'cost_episodes':1})
    group={'support':[{'condition_id':f'c{i}','split':'support','seed':123+i,
                       'object_mass_kg':.1 if i==0 else .4,'public_goal':[.62,.12,.021]} for i in range(2)]}
    value=learning.learn(tmp_path,tmp_path,'cpu-fixture',{},base,group,'feedback','fixture',[], 'fixture-id',0)
    assert len(jobs)==2 and [j['condition']['seed'] for j in jobs]==[124,123]
    assert requests[2]['current_program']==program and requests[2]['current_memory']=='my note'
    assert requests[3]['history'][-1]['practice_handle']=='practice-1'
    assert requests[4]['history'][-1]['practice_handle']=='practice-0'
    assert requests[4]['current_memory']=='second trial'
    assert value['payload']['skill']==program and value['payload']['memory']=='final note'
    for request in requests:
        learning.assert_public(request)
        assert 'query' not in request


def test_replication_global_freeze_barrier_and_registered_query_orders(tmp_path,monkeypatch):
    import json
    import threading

    import physicalevobench.core.replication as replication
    from physicalevobench.core.artifact import freeze
    from physicalevobench.core.learning import artifact
    from physicalevobench.core.state_config import reference
    from physicalevobench.development.place import starter_program

    base=reference({'reference_config':{}})
    groups=[]
    for b in range(8):
        groups.append({split:[{'condition_id':f'{b}-{split}-{i}','split':split,'seed':10000*b+i+(1000 if split=='query' else 0),
                              'object_mass_kg':.1 if i%2==0 else .4,'public_goal':[.6,.12,.021]} for i in range(n)]
                       for split,n in [('support',4),('query',16)]})
    (tmp_path/'configs/reliability').mkdir(parents=True)
    (tmp_path/'configs/reliability/public_context_v3.json').write_text('CPU fixture')
    monkeypatch.setattr(replication,'command',lambda argv,**kw:{'stdout':'' if 'status' in argv else 'CPU-fixture-source'})
    monkeypatch.setattr(replication,'validate_contract',lambda *args:({},base))
    monkeypatch.setattr(replication,'manifest',lambda *args,**kwargs:groups)
    lock=threading.Lock()
    completed=[]
    observed={}
    def fake_learn(root,directory,source,cfg,base,group,name,model,provider,run_id,gpu):
        path=directory/name
        path.mkdir()
        value=freeze(artifact(base,starter_program(),source,run_id,name,0,''),path/'artifact.json')
        with lock:
            completed.append((directory.name,name))
        return value
    def fake_search(root,directory,source,cfg,base,group,run_id,gpu):
        return fake_learn(root,directory,source,cfg,base,group,'search',None,None,run_id,gpu)
    class Session:
        def __init__(self,root,out,source,cfg,gpu):
            assert len(completed)==24 and (out.parent.parent/'all_frozen.json').exists()
            self.key=(out.parent.name,out.name)
            observed[self.key]=[]
        def ready(self):
            pass
        def trial(self,job):
            observed[self.key].append(job['condition']['condition_id'])
        def close(self):
            pass
    monkeypatch.setattr(replication,'learn',fake_learn)
    monkeypatch.setattr(replication,'score_search',fake_search)
    monkeypatch.setattr(replication,'NativeSession',Session)
    monkeypatch.setattr(replication,'audit_and_summarize',lambda out:{'CPU_contract_only':True})
    out=tmp_path/'study'
    (tmp_path/'unused').write_text('{}')
    replication.run(tmp_path,out,tmp_path/'unused',[0,1,2,3])
    reg=json.loads((out/'registration.json').read_text())
    assert len(observed)==40
    for (block,method),conditions in observed.items():
        i=int(block.removeprefix('instance-'))
        arm=method.removeprefix('test-')
        assert conditions==[groups[i]['query'][j]['condition_id'] for j in reg['query_order_by_arm'][i][arm]]


def test_cached_mass_is_not_actual_physx_parameter_evidence():
    import copy

    from physicalevobench.core.parameter_transport import validate

    inertia=[[.0001536,0.,0.,0.,.0001536,0.,0.,0.,.0001536]]
    shadow={'mass':[[.4]],'inertia':[inertia]}
    model={'status':'MEASURED','mass':[[.4]],'inertia':inertia}
    assert validate(shadow,model,.4)[0]
    stale=copy.deepcopy(model)
    stale['mass']=[[.1]]
    assert validate(shadow,stale,.4)==(False,'physx_model_shadow_mismatch:mass')
    stale=copy.deepcopy(model)
    stale['inertia'][0][0]=.0000384
    assert validate(shadow,stale,.4)==(False,'physx_model_shadow_mismatch:inertia')
    assert not validate(shadow,{'status':'not_measured'},.4)[0]
    assert not validate(shadow,model,float('nan'))[0]
