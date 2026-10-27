import copy
import json

import pytest

from physicalevobench.core.artifact import freeze, load
from physicalevobench.core.audit import assert_public
from physicalevobench.core.metrics import compare, place_metrics
from physicalevobench.core.program import Program, ProgramFSM, initial_program
from physicalevobench.v02.reference_artifact import ReferenceSkill


def test_private_fields_are_rejected_at_every_nested_level():
    assert_public({'history':[{'public_state_samples':[{'object_position':[0,0,0]}]}]})
    for key in ('seed','object_mass_kg','heldout','evaluator_config'):
        with pytest.raises(ValueError,match='Private'):
            assert_public({'history':[{'feedback':{key:1}}]})


def test_program_rejects_undefined_edges_nonfinite_code_and_unbounded_retries():
    original=initial_program().to_dict()
    for key,value in [('target','eval(os.environ)'),('timeout_s',float('nan')),('next','missing')]:
        bad=copy.deepcopy(original)
        bad['nodes'][0][key]=value
        with pytest.raises(ValueError):
            Program.from_dict(bad)
    bad=copy.deepcopy(original)
    bad['nodes'][0]['seed']=42
    with pytest.raises(ValueError):
        Program.from_dict(bad)
    with pytest.raises(ValueError):
        Program.from_dict({**original,'max_retries':3})
    assert Program.from_dict(original).sha256==initial_program().sha256


def test_program_pose_guard_cannot_be_passed_by_waiting():
    obs={'ee_position':[0,0,1],'object_position':[.5,0,.02],
         'goal_position':[.5,0,.3],'object_velocity':[0,0,0],
         'finger_position':[.04,.04],'cube_contact_force':[0,0],'orientation_error':0.}
    fsm=ProgramFSM(initial_program())
    for _ in range(500):
        result=fsm.update(obs,.02)
    assert result['program_node']=='approach' and result['gripper']=='open'
    for _ in range(4):
        result=fsm.update({**obs,'ee_position':[.5,0,.12]},.02)
    assert result['program_node']=='descend'


def place_frames(count=26,**changes):
    initial={'object_position':[[.5,0,.05]]}
    result=[{'control_step':0,'object_position':[[.5,0,.12]],'object_velocity':[[0]*6],
             'ee_position_world':[[.5,0,.12]],'finger_position':[.02,.02]},
            {'control_step':1,'object_position':[[.62,.12,.12]],'object_velocity':[[0]*6],
             'ee_position_world':[[.62,.12,.12]],'finger_position':[.02,.02]}]
    for i in range(count):
        result.append({'control_step':i+2,'object_position':[[.62,.12,.021]],
                       'object_velocity':[[0]*6],'ee_position_world':[[.62,.12,.15]],
                       'finger_position':[.04,.04],**changes})
    return initial,result


def test_place_requires_physical_release_transport_and_full_stable_span():
    initial,frames=place_frames()
    assert place_metrics(initial,frames)['success']
    assert not place_metrics(*place_frames(count=25))['success']
    assert not place_metrics(*place_frames(finger_position=[.02,.02]))['success']
    assert not place_metrics(*place_frames(ee_position_world=[[.62,.12,.03]]))['success']
    no_lift=[{**f,'control_step':i} for i,f in enumerate(frames[2:])]
    assert not place_metrics(initial,no_lift)['success']  # no prior lift
    assert not place_metrics(*place_frames(object_velocity=[[.2,0,0,0,0,0]]))['success']


def test_artifact_covers_memory_executor_and_program_not_only_two_parameters(tmp_path):
    skill=ReferenceSkill('a'*64)
    p={'schema':'core-artifact-1','track':'P','participant':'model/code-1','interface':'v1',
       'executor':'source-1','task':'T0','scoring':'s1','initial_reference':'a'*64,
       'skill':skill.to_dict(),'memory':'learned','budget_used':8,'learning_run_id':'run-0'}
    a=freeze(p,tmp_path/'a.json')
    b=freeze({**p,'memory':''},tmp_path/'b.json')
    assert a['effective_artifact_hash']!=b['effective_artifact_hash']
    c=freeze({**p,'executor':'source-2'},tmp_path/'c.json')
    assert a['effective_artifact_hash']!=c['effective_artifact_hash']
    assert load(tmp_path/'a.json')==a
    a['payload']['skill']['minimum_close_s']=.7
    (tmp_path/'a.json').write_text(json.dumps(a))
    with pytest.raises(ValueError,match='identity'):
        load(tmp_path/'a.json')


def test_signed_paired_gains_do_not_require_promotion_or_positive_effect():
    result=compare({'a':True,'b':True},{'a':False,'b':True})
    assert result['gain']==-.5
    with pytest.raises(ValueError,match='Paired'):
        compare({'a':True},{'b':True})


def test_task_library_reuses_exact_t0_and_exposes_replaceable_place_graph():
    from physicalevobench.core.library import SkillLibrary, from_reference_skill
    initial=ReferenceSkill('a'*64,.12,.7)
    library=from_reference_skill(initial)
    restored=SkillLibrary.from_dict(library.to_dict())
    assert restored.lift==initial
    nodes={n['id']:n for n in restored.place.nodes}
    assert nodes['approach']['offset_m']==.12
    assert nodes['close']['minimum_s']==.7
    changed=library.to_dict()
    changed['tasks']['place']['nodes'][0]['next']='close'
    assert SkillLibrary.from_dict(changed).sha256!=restored.sha256
    with pytest.raises(ValueError):
        SkillLibrary.from_dict({**changed,'test_results':{}})


def test_cyclic_program_exhaustion_latches_open_instead_of_resetting_budget():
    from physicalevobench.core.program import node
    program=Program((node('a','object_above','close','always','b',mode='close',on_timeout='b'),
                     node('b','object_above','close','always','a',mode='close',on_timeout='a')),start='a')
    fsm=ProgramFSM(program)
    obs={'ee_position':[.5,0,.1],'object_position':[.5,0,.02],'goal_position':[.5,0,.3],
         'object_velocity':[0,0,0],'finger_position':[.02,.02],
         'cube_contact_force':[10,10],'orientation_error':0.}
    for _ in range(500):
        result=fsm.update(obs,.02)
    assert result['phase']=='failed' and result['gripper']=='open'
    assert fsm.transitions==65
    for _ in range(20):
        assert fsm.update(obs,.02)['phase']=='failed'
    assert fsm.transitions==65


def test_place_does_not_bridge_missing_control_samples():
    initial,frames=place_frames()
    frames[10]['control_step']=100
    with pytest.raises(ValueError,match='Continuous'):
        place_metrics(initial,frames)


def test_evidence_extraction_rejects_absolute_paths_and_links():
    import io
    import tarfile

    from physicalevobench.core.delivery import safe_members
    for name,kind in [('../escape',tarfile.REGTYPE),('/absolute',tarfile.REGTYPE),('link',tarfile.SYMTYPE)]:
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode='w') as archive:
            info=tarfile.TarInfo(name)
            info.type=kind
            archive.addfile(info)
        buf.seek(0)
        with tarfile.open(fileobj=buf,mode='r') as archive:
            with pytest.raises(ValueError,match='safe'):
                list(safe_members(archive))


def test_program_skip_probe_keeps_current_grasp_frame_instead_of_initial_ee_offset():
    value=initial_program(True).to_dict()
    for n in value['nodes']:
        if n['id']=='close':
            n['next']='lift'
    fsm=ProgramFSM(Program.from_dict(value))
    obs={'ee_position':[.5,0,.12],'object_position':[.5,0,.02],
         'goal_position':[.5,0,.3],'object_velocity':[0,0,0],
         'finger_position':[.02,.02],'cube_contact_force':[10,10],'orientation_error':0.}
    for _ in range(3):
        fsm.update(obs,.02)
    obs={**obs,'ee_position':[.5,0,.025]}
    for _ in range(3+14):
        decision=fsm.update(obs,.02)
    assert decision['program_node']=='lift'
    assert fsm.offset==pytest.approx([0,0,.005])


def test_place_feedback_uses_place_result_instead_of_auxiliary_lift_flags(tmp_path):
    import gzip

    from physicalevobench.core.pilot import public_feedback
    trace=tmp_path/'trace.jsonl.gz'
    with gzip.open(trace,'wt') as stream:
        stream.write(json.dumps({'step':0,'policy_diagnostics':{'public':{},'decision':{'phase':'hold'}}})+'\n')
    row={'success':True,'steps':1000,'failure_type':'effective_task_not_completed',
         'termination_reason':'horizon','trace_artifact':trace.name,
         'diagnostic':{'holding':{'maximum_holding_span_s':0.},'first_violation':None,'hard_boundary_terminated':False},
         'place':{'success':True,'maximum_stable_span_s':.8}}
    feedback=public_feedback(tmp_path,row)
    assert feedback['effective_success'] and feedback['failure_reason'] is None
    assert feedback['holding_span_s']==.8
    row['success']=False
    row['failure_type']=None
    assert public_feedback(tmp_path,row)['failure_reason']=='place_task_not_completed'
