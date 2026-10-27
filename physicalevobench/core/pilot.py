"""Actual model learning, matched search, freeze/reload and artifact deletion pilot."""

import argparse
import json
import os
import random
import shutil
import subprocess
import time
from functools import partial
from pathlib import Path

from physicalevobench.core.artifact import freeze, load
from physicalevobench.core.model import ParticipantProcess
from physicalevobench.core.runtime import NativeSession
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.stability.audit import read
from physicalevobench.v02.audit import records
from physicalevobench.v02.reference_artifact import ReferenceSkill, digest
from physicalevobench.v02.reference_artifact import load as load_reference


INSTRUCTIONS='''You are a PhysicalEvoBench experimental participant, not a repository developer.
Use ONLY this public JSON context. Do not use local shell, filesystem, MCP or web tools.
Your editable space is Reference Parameter Adaptation P, not autonomous program generation.
Common initial ability is a normal calibrated state-based grasp/probe/lift reference with
bounded joint integral compensation. Edit only approach_clearance_m [.08,.12] and
minimum_close_s [.20,.70]. No hidden condition/physics/evaluator modification is allowed.
The public task is Lift-Hold: ten seconds, object within .05m of goal with speed<=.2m/s
for >=.30s. All conditions expose state observations; unknown physical mass is not supplied.
Choose your own candidate from feedback, use tool run_trial to propose and execute it on
one authorized training handle, or freeze to retain an executable candidate and short
persistent memory. run_trial includes validated proposal registration. No developer-written
failure-to-fix mapping is provided. Your final freeze may retain initial parameters; no
positive gain is required. Trial maximum8. You may reuse handles. Failed trials cost budget.
Freeze no later than when physical budget is exhausted. Only your frozen artifact survives
into new test instances; no test feedback is available during training. Return exactly the
schema-specified JSON tool call. The training_condition_handle is ignored for freeze.
'''


def fresh_conditions(root,parent,extra_excluded=()):
    excluded=published_seeds(root)
    excluded.update(extra_excluded)
    for path in parent.glob('peb-*/registration.json'):
        excluded.update(registered_seed_values(read(path)))
    rng=random.Random(2026102702)
    groups={}
    for split in ('train','heldout'):
        groups[split]=[]
        for i in range(4):
            seed=rng.randrange(2**31)
            while seed in excluded:
                seed=rng.randrange(2**31)
            excluded.add(seed)
            groups[split].append({'condition_id':f'core-pilot-{split}-{i:02d}',
                                 'seed':seed,'split':split,'object_mass_kg':.1 if i<2 else .4})
    return groups


def worker_config(base,budget):
    checkpoint=str(Path(os.environ.get('PHYSICALEVOBENCH_CHECKPOINT',
                               '~/models/physicalevobench/franka_lift/model_1999.pt')).expanduser().absolute())
    return {'checkpoint_path':checkpoint,'checkpoint_sha256':base['checkpoint_sha256'],
            'policy_config_sha256':sha256(Path(checkpoint).parent/'params/agent.yaml'),
            'mode':'FixedHorizonDiagnostic','execution_layer':'TargetBounded',
            'reference_controller':'StateBasedReference','reference_config':base['reference_config'],
            'horizon_s':base['horizon_s'],'task_version':base['task_version'],'physical_budget':budget}


def payload(base,skill,participant,run,budget,memory='',executor_commit='unregistered'):
    return {'schema':'core-artifact-1','track':'P','participant':participant,
            'interface':'core-participant-1','executor':'TargetBounded-reference-v2-1/'+executor_commit,
            'task':base['task_version'],'scoring':'v02-post-physics-holding-1',
            'initial_reference':digest(base),'skill':skill.to_dict(),'memory':memory,
            'budget_used':budget,'learning_run_id':run}


def public_feedback(directory,row):
    diagnostic=row['diagnostic']
    trace=records(Path(directory)/row['trace_artifact'])
    samples=[{'step':s['step'],**s['policy_diagnostics']['public'],
              'phase':s['policy_diagnostics']['decision']['phase']} for s in trace[::50]]
    return {'effective_success':row['success'],'steps':row['steps'],'cost_episodes':1,
            'failure_reason':(None if row['success'] else ('place_task_not_completed' if row.get('place') else row['failure_type'])),
            'termination_reason':row['termination_reason'],
            'holding_span_s':(row['place']['maximum_stable_span_s'] if row.get('place') else
                              diagnostic['holding']['maximum_holding_span_s']),
            'registered_position_violation':diagnostic['first_violation'] is not None,
            'public_state_samples':samples,'hard_event':diagnostic['hard_boundary_terminated']}


def compact_history(history):
    """All trial outcomes, but full sampled trajectory only for two recent trials.

    Lossless raw evidence and complete tool responses remain outside the model
    request. This is a public, fixed context policy, not hidden feedback selection.
    """
    result=json.loads(json.dumps(history))
    for item in result[:-2]:
        feedback=item.get('feedback',{})
        feedback.pop('public_state_samples',None)
    return result


def trial_job(base,skill,condition,identity,index):
    return {'episode_id':f'episode-{index:03d}','condition':condition,
            'reference_config':skill.configuration(base),'identity':identity}


def run(root,out,reference,gpu,model,b1,after_b1=False,participant_command=None,resume_prelaunch=False,after_native=None):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit protocol and implementation before pilot reservation')
    if not b1.exists():
        raise ValueError('B1 registered diagnosis is required')
    if read(b1/'status.json')['status']!='COMPLETED' and not after_b1:
        raise ValueError('Finish B1 before learning pilot')
    for previous in out.parent.glob('peb-*/registration.json'):
        if resume_prelaunch and previous.parent==out:
            continue
        if (read(previous).get('schema')=='core-pilot-1' and
                read(previous.parent/'status.json')['status']!='CANCELLED_BEFORE_LAUNCH'):
            raise ValueError('The single initial Agent pilot was already reserved; no outcome-based retry')
    base=load_reference(reference)
    source_commit=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    make_payload=partial(payload,executor_commit=source_commit)
    transport=participant_command or ['codex']
    cli_version=(subprocess.check_output(['codex','--version'],text=True).strip()
                 if transport==['codex'] else 'generic-stdin-'+digest({'command':transport,'model':model}))
    if resume_prelaunch:
        reg=read(out/'registration.json')
        prior_status=read(out/'status.json')
        if (prior_status['status']!='FAILED' or list(out.rglob('launch.json')) or
                (out/'model_calls').exists() or (out/'frozen.json').exists()):
            raise ValueError('Only a failed prelaunch with zero model/physics work can resume')
        if (reg['baseline_reference_sha256']!=sha256(reference) or reg['model']!=model or
                reg['gpu']!=gpu or reg['participant_transport']!=cli_version):
            raise ValueError('Prelaunch recovery must preserve registered inputs')
        save_json(out/'prelaunch_recovery.json',{'at':now(),'original_registration_sha256':sha256(out/'registration.json'),
                  'previous_status':prior_status,'recovery_launcher_commit':source_commit,
                  'physical_attempts_before_recovery':0,'model_learning_calls_before_recovery':0,
                  'reason':'Prerequisite published COMPLETED before its derived result file; recover same untouched reservation/conditions.'})
        source_commit=reg['source_commit']
        make_payload=partial(payload,executor_commit=source_commit)
        groups,order=reg['conditions'],reg['evaluation_order']
    else:
        groups=fresh_conditions(root,out.parent,registered_seed_values(read(b1/'registration.json')))
        out.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(reference,out/'baseline_reference.json')
        order=['frozen','search','feedback','ablation']
        random.Random(2026102703).shuffle(order)
        reg={'schema':'core-pilot-1','registered_at':now(),'source_commit':source_commit,
             'reference_source_commit':base['source_commit'],'baseline_reference_sha256':sha256(reference),
             'conditions':groups,'physical_budget':32,'training_per_method':8,'heldout_per_arm':4,
             'model':model,'participant_transport':cli_version,'gpu':gpu,'evaluation_order':order,
             'b1_registration_sha256':sha256(b1/'registration.json'),
             'protocol':'docs/core/CORE_PROTOCOL_20261027.md','track':'P',
             'purpose':'actual model/interface pilot; P efficacy unconfirmed, not S program evolution',
             'computational_budget':{'calls':12,'input_tokens':250000,'output_tokens':24000,'timeout_per_call_s':120},
             'methods':['frozen','score_only_search','feedback_persistent','artifact_deletion'],
             'online_model_calls_per_test_episode':0}
        save_json(out/'registration.json',reg)
    save_json(out/'status.json',{'status':'QUEUED','at':now()})
    while (read(b1/'status.json')['status']=='RUNNING' or
           (read(b1/'status.json')['status']=='COMPLETED' and not (b1/'parameter_space_results.json').exists())):
        time.sleep(5)
    if read(b1/'status.json')['status']!='COMPLETED':
        raise ValueError('B1 prerequisite failed; no model or native learning launch')
    save_json(out/'b1_gate.json',{'at':now(),'result_sha256':sha256(b1/'parameter_space_results.json')})
    if after_native:
        while read(after_native/'status.json')['status'] in ('RUNNING','QUEUED'):
            time.sleep(5)
        if any(not (p.parent/'process.json').exists() for p in after_native.rglob('launch.json')):
            raise ValueError('Preceding native worker has not exited; refusing concurrent physics')
    save_json(out/'status.json',{'status':'RUNNING','at':now()})
    initial=ReferenceSkill(digest(base))
    artifacts={}
    artifacts['frozen']=freeze(make_payload(base,initial,'frozen-reference-v2','not_applicable',0),out/'frozen.json')
    feedback_run='core-pilot-feedback-0'
    freeze(make_payload(base,initial,f'{model}/{cli_version}',feedback_run,0),out/'feedback-budget0.json')
    freeze(make_payload(base,initial,'seeded-uniform-score-search-1','core-pilot-search-0',0),out/'search-budget0.json')
    handles={f'train-{i}':c for i,c in enumerate(groups['train'])}
    # Predeclared candidate distribution: normal initial then seven independent
    # uniform candidates. Search consumes only a boolean score, not diagnostics.
    rng=random.Random(2026102704)
    candidates=[initial]+[ReferenceSkill(digest(base),rng.uniform(.08,.12),rng.uniform(.2,.7)) for _ in range(7)]
    save_json(out/'search_candidates.json',[s.to_dict() for s in candidates])
    for method in ('feedback','search'):
        session=NativeSession(root,out/f'train-{method}',source_commit,worker_config(base,8),gpu)
        history=[]
        best=initial
        best_score=-1
        memory=''
        model_process=None
        if method=='feedback':
            model_process=ParticipantProcess(transport,model,out/'model_calls')
        try:
            session.ready()
            for call in range(12 if method=='feedback' else 8):
                if method=='feedback':
                    request={'instructions':INSTRUCTIONS,'initial_skill':initial.to_dict(),
                             'allowed_training_handles':list(handles),'remaining_physical_episodes':8-session.used,
                             'maximum_model_calls_remaining':12-call,'history':compact_history(history)}
                    answer=model_process.call(request)
                    save_json(out/f'feedback-tool-{call:02d}.json',answer)
                    if set(answer)!= {'tool','approach_clearance_m','minimum_close_s','training_condition_handle','memory'}:
                        raise ValueError('Participant submitted unsupported tool fields')
                    skill=ReferenceSkill(digest(base),answer['approach_clearance_m'],answer['minimum_close_s'])
                    if not isinstance(answer['memory'],str) or len(answer['memory'])>4000:
                        raise ValueError('Unbounded participant memory')
                    if answer['tool']=='freeze':
                        best,memory=skill,answer['memory']
                        break
                    if answer['tool']!='run_trial' or answer['training_condition_handle'] not in handles:
                        raise ValueError('Unauthorized participant tool or handle')
                    if session.used>=8:
                        raise ValueError('Participant exceeded physical trial budget')
                    condition=handles[answer['training_condition_handle']]
                else:
                    skill=candidates[call]
                    condition=groups['train'][call%4]
                identity={'learning_run_id':feedback_run if method=='feedback' else 'core-pilot-search-0',
                          'budget_used':session.used,'checkpoint_index':0,'effective_artifact_hash':skill.sha256,
                          'task_id':base['task_version'],'split_id':'train','condition_id':condition['condition_id'],
                          'physical_replay_id':f'{method}-{session.used}','execution_profile':'TargetBounded-reference-v2-1'}
                candidate=make_payload(base,skill,f'{model}/{cli_version}' if method=='feedback' else 'seeded-uniform-score-search-1',
                                  identity['learning_run_id'],session.used,answer['memory'] if method=='feedback' else '')
                identity['effective_artifact_hash']=digest(candidate)
                job=trial_job(base,skill,condition,identity,session.used)
                job['candidate_artifact']=candidate
                row=session.trial(job)
                if method=='feedback':
                    history.append({'tool':'run_trial','candidate':skill.to_dict(),
                                    'training_condition_handle':answer['training_condition_handle'],
                                    'hypothesis_or_memory':answer['memory'],
                                    'feedback':public_feedback(session.out,row)})
                else:
                    score=int(row['success'])
                    if score>best_score:
                        best,best_score=skill,score
                    history.append({'candidate':skill.to_dict(),'score':score,'cost_episodes':1})
            else:
                if method=='feedback':
                    raise ValueError('No participant freeze within computational budget')
        finally:
            session.close()
        save_json(out/f'{method}-training-history.json',history)
        participant=f'{model}/{cli_version}' if method=='feedback' else 'seeded-uniform-score-search-1'
        artifact=freeze(make_payload(base,best,participant,
                                feedback_run if method=='feedback' else 'core-pilot-search-0',
                                session.used,memory),out/f'{method}.json')
        artifacts[method]=artifact
        # Freeze ablation before all heldout data: same participant/executor and
        # initial content; no retraining and no inference from hash existence.
        if method=='feedback':
            artifacts['ablation']=freeze(make_payload(base,initial,participant,feedback_run,0),out/'ablation.json')
    save_json(out/'all_snapshots_frozen.json',{'at':now(),'artifacts':{k:v['effective_artifact_hash'] for k,v in artifacts.items()}})
    for arm_index,arm in enumerate(order):
        # Reload exclusively from disk into a new native process. No training
        # history, model conversation or heldout score reaches the participant.
        artifact=load(out/f'{arm}.json')
        skill=ReferenceSkill.from_dict(artifact['payload']['skill'])
        session=NativeSession(root,out/f'test-{arm}',source_commit,worker_config(base,4),gpu)
        try:
            session.ready()
            conditions=groups['heldout'][arm_index:]+groups['heldout'][:arm_index]
            for i,c in enumerate(conditions):
                identity={'learning_run_id':artifact['payload']['learning_run_id'],
                          'budget_used':artifact['payload']['budget_used'],'checkpoint_index':1,
                          'effective_artifact_hash':artifact['effective_artifact_hash'],'task_id':base['task_version'],
                          'split_id':'heldout','condition_id':c['condition_id'],'physical_replay_id':f'{arm}-{i}',
                          'execution_profile':'TargetBounded-reference-v2-1'}
                session.trial(trial_job(base,skill,c,identity,i))
        finally:
            session.close()
    from physicalevobench.core.audit import audit_pilot
    result=audit_pilot(out)
    save_json(out/'status.json',{'status':'COMPLETED','finished_at':now()})
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--reference',required=True)
    p.add_argument('--b1',required=True)
    p.add_argument('--gpu',type=int,default=2)
    p.add_argument('--model',default='gpt-6.1-terra')
    p.add_argument('--after-b1',action='store_true')
    p.add_argument('--resume-prelaunch',action='store_true',help='Recover identical reservation only before any model/physics work')
    p.add_argument('--after-native',help='Serialize after an already running native study')
    p.add_argument('--participant-command',type=json.loads,help='JSON argv array; default optional Codex CLI')
    a=p.parse_args()
    b1=Path(a.b1)
    out=Path(a.output).absolute()
    try:
        run(Path.cwd(),out,Path(a.reference),a.gpu,a.model,b1,a.after_b1,a.participant_command,a.resume_prelaunch,Path(a.after_native) if a.after_native else None)
    except Exception as error:
        if out.exists():
            save_json(out/'status.json',{'status':'FAILED','error':str(error),'at':now()})
        raise


if __name__=='__main__':
    main()
