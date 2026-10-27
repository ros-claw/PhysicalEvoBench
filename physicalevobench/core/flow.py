"""Gated two-task pilot: zero-learning transfer, program learning and retention."""

import argparse
import copy
import json
import random
from pathlib import Path

from physicalevobench.core.artifact import freeze, load
from physicalevobench.core.audit import assert_public, audit_session
from physicalevobench.core.library import SkillLibrary, call_schema, from_reference_skill
from physicalevobench.core.metrics import compare
from physicalevobench.core.model import ParticipantProcess
from physicalevobench.core.pilot import compact_history, fresh_conditions, public_feedback, worker_config
from physicalevobench.core.runtime import NativeSession
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import ReferenceSkill, digest
from physicalevobench.v02.reference_artifact import load as load_reference


S_INSTRUCTIONS='''You are a trusted experimental PhysicalEvoBench participant, not a developer.
Use only the public JSON context; no shell, filesystem, MCP or web tools.
Task: Pick-Transport-Place on the same table, maximum20s. Target XY is initial cube
XY+(.12,.12)m, supported center Z=.021m. Must lift >=.05m above reset height and travel
>=.08m, release with both fingers>=.035m, EE/cube separation>=.06m, object within horizontal
.05m /vertical .025m of target, linear speed<=.10m/s for continuous .50s. New test conditions
are unavailable. Fixed executor: geometric DLS IK, gravity compensation and bounded
integral in modes lift/hold, shared target limits/rates. Update only the JSON task library.
You can replace place graph targets, gripper actions, guards, branch/timeout edges,
dwell/tolerances and bounded retries; retain or change inherited T0 reference parameters.
Preserve useful T0 ability if possible. Do not invent fields or alter actuators/scoring.
Guard rules: pose distance<=tolerance plus orientation<=.15rad; bilateral >=.5N normal
contact each and nonempty aperture; follow >=.02m object lift and <=.025m relative drift;
object_goal uses T0 goal; elapsed and always require minimum_s. Dwells apply to all guards.
Targets: object_above/object_grasp use current object+offset_m vertically; anchor captures
EE when entering close/recover; probe/retreat_anchor add offset_m to anchor; goal_offset
is T0 goal plus measured grasp relative offset; lift_initial is initial cube XY and Z+
offset_m plus grasp offset; place_above/place_lower/place_retreat use public place target
plus vertical offset_m and grasp offset. Leaving close/probe into lift captures the current grasp offset; close→probe also captures object-follow reference.
Modes approach/descend/close/probe/lift/hold/release/recover/failed select executor state;
integral is active only lift/hold. All other graph choices are participant-controlled.
Program bounds:1..16 nodes, defined edges, max_retries0..2, at most64 node transitions,
tolerance .005..06m, dwell .02..5s, minimum0..1s, timeout .1..20s, offset0..15m.
At most8 physical learning trials and12 model calls, no improvement requirement. Return
run_trial with your candidate library and authorized handle, or freeze with final library
and <=4000-character persistent memory. run_trial includes proposal registration. Freeze
when trials are exhausted. Only frozen library/memory crosses into new test instances.
'''


def artifact(base,library,participant,run,budget,memory,source):
    return {'schema':'core-artifact-1','track':'S','participant':participant,
            'interface':'core-participant-library-1','executor':'TargetBounded-reference-v2-1/'+source,
            'task':'T0-and-core-place-h20-v2-dev','scoring':'holding-1/place-1',
            'initial_reference':digest(base),'skill':library.to_dict(),'memory':memory,
            'budget_used':budget,'learning_run_id':run}


def job_for(base,library,task,condition,identity,index):
    job={'episode_id':f'episode-{index:03d}','condition':condition,'identity':identity,
         'reference_config':library.lift.configuration(base)}
    if task=='place':
        job['program']=library.place.to_dict()
    return job


def cfg_for(base,task,budget):
    cfg=worker_config(base,budget)
    if task=='place':
        cfg.update(core_task='place',horizon_s=20.,task_version='core-place-h20-v2-dev')
    return cfg


def identity_for(value,task,condition,split,index):
    p=value['payload']
    return {'learning_run_id':p['learning_run_id'],'budget_used':p['budget_used'],
            'checkpoint_index':1,'effective_artifact_hash':value['effective_artifact_hash'],
            'task_id':'core-place-h20-v2-dev' if task=='place' else 'state-reference-h10-v1',
            'split_id':split,'condition_id':condition['condition_id'],
            'physical_replay_id':str(index),'execution_profile':p['executor']}


def evaluate(root,out,source,base,gpu,arm,value,task,conditions):
    library=SkillLibrary.from_dict(value['payload']['skill'])
    session=NativeSession(root,out/arm,source,cfg_for(base,task,4),gpu)
    try:
        session.ready()
        for i,c in enumerate(conditions):
            session.trial(job_for(base,library,task,c,identity_for(value,task,c,'heldout',i),i))
    finally:
        session.close()
    return audit_session(out/arm)


def summarize(out):
    out=Path(out)
    reg=json.loads((out/'registration.json').read_text())
    workers={}
    for child in sorted(out.iterdir()):
        if child.is_dir() and (child/'server_receipt.json').exists():
            workers[child.name]=audit_session(child)
    scores={name:{r['condition_id']:r['success'] for r in data} for name,data in workers.items()}
    base=load_reference(out/'baseline_reference.json')
    final_freeze=json.loads((out/'all_T1_snapshots_frozen.json').read_text())
    for name,data in workers.items():
        if name.startswith('learn-'):
            allowed=reg['T1_train']
            if len(data)>8:
                raise ValueError('T1 training budget exceeded')
        else:
            allowed=reg['T0_retention'] if name.startswith('retention-') else reg['T1_heldout']
            if {r['condition_id'] for r in data}!={c['condition_id'] for c in allowed}:
                raise ValueError('Missing paired task-flow conditions')
            method=name.split('-',1)[1]
            value=load(out/f'{method}-{"initial" if name.startswith("transfer-") else "final"}.json')
            library=SkillLibrary.from_dict(value['payload']['skill'])
            if name.startswith(('final-','retention-')):
                if json.loads((out/name/'launch.json').read_text())['started_at']<=final_freeze['at']:
                    raise ValueError('Final test started before all T1 snapshots froze')
                if final_freeze['hashes'][method]!=value['effective_artifact_hash']:
                    raise ValueError('Final T1 artifact changed after freeze')
            for i,row in enumerate(data):
                job=json.loads((out/name/'requests'/f'{i:03d}.json').read_text())
                if (row['core_identity']['effective_artifact_hash']!=value['effective_artifact_hash'] or
                        job['reference_config']!=library.lift.configuration(base) or
                        (not name.startswith('retention-') and job['program']!=library.place.to_dict())):
                    raise ValueError('Effective test program differs from the frozen library')
        for i,row in enumerate(data):
            job=json.loads((out/name/'requests'/f'{i:03d}.json').read_text())
            if job['condition'] not in allowed:
                raise ValueError('Unregistered task-flow condition')
    for method in ('frozen','feedback','search'):
        prior=load(out/f'provenance-T0-{method}.json')
        initial=load(out/f'{method}-initial.json')
        if SkillLibrary.from_dict(initial['payload']['skill']).lift.to_dict()!=prior['payload']['skill']:
            raise ValueError('Initial library did not inherit exact T0 experience')
    for request in (out/'S_model_calls').glob('call-*/request.json'):
        assert_public(json.loads(request.read_text()))
    usages=[json.loads(p.read_text()) for p in sorted((out/'S_model_calls').glob('call-*/usage.json'))]
    model_cost={'calls':len(usages),'input_tokens':sum(u['input_tokens'] for u in usages),
                'output_tokens':sum(u['output_tokens'] for u in usages)}
    if model_cost!=json.loads((out/'S_model_calls/budget.json').read_text()) or any(
            model_cost[k]>reg['computational_budget'][k] for k in model_cost):
        raise ValueError('S actual-model computation accounting mismatch')
    outputs=[json.loads(p.read_text()) for p in sorted((out/'S_model_calls').glob('call-*/response.json'))]
    retained=load(out/'feedback-final.json')
    if (outputs[-1]['tool']!='freeze' or outputs[-1]['library']!=retained['payload']['skill'] or
            outputs[-1]['memory']!=retained['payload']['memory'] or
            sum(o['tool']=='run_trial' for o in outputs)!=len(workers['learn-feedback'])):
        raise ValueError('S retained experience did not originate from actual model tools')
    pilot=reg['t0_pilot_results']
    gains={}
    for method in ('feedback','search'):
        gains[method]={
            'zero_learning_transfer':compare(scores['transfer-frozen'],scores['transfer-'+method]),
            'T1_learning_gain':compare(scores['transfer-'+method],scores['final-'+method]),
            'T0_retention_change':compare(pilot['arms'][method]['scores'],scores['retention-'+method])}
    total=sum(len(data) for data in workers.values())
    if total>44:
        raise ValueError('Task-flow episode budget exceeded')
    result={'schema':'core-flow-results-1','audit':'PASS','physical_episodes':total,
            'scores':{name:{'successes':sum(values.values()),'episodes':len(values),'scores':values}
                      for name,values in scores.items()},'changes':gains,
            'feedback_T1_learning_phases':1,'search_T1_learning_phases':1,
            'independent_sequential_trajectories_per_method':1,'model_cost':model_cost,
            'control_steps':sum(r['steps'] for data in workers.values() for r in data),
            'physics_samples':sum(r['diagnostic']['physics_samples'] for data in workers.values() for r in data),
            'scope':'One sequential learning trajectory/method. P→T1 transfer is parameter reuse; '
                    'T1 learning is bounded skill-program editing. No cross-learning stability claim.'}
    save_json(out/'flow_results.json',result)
    return result


def run(root,out,pilot,confirmation,gpu):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit S protocol and task-flow code before registration')
    for previous in out.parent.glob('peb-*/registration.json'):
        if json.loads(previous.read_text()).get('schema')=='core-flow-1':
            raise ValueError('Initial task-flow budget already reserved; no outcome-based retries')
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    base=load_reference(pilot/'baseline_reference.json')
    pilot_result=json.loads((pilot/'pilot_results.json').read_text())
    if pilot_result['audit']!='PASS':
        raise ValueError('Actual Agent pilot must complete first')
    gate=json.loads((confirmation/'place_results.json').read_text())
    if gate['independent_gate_passed'] is not True:
        raise ValueError('T1 independent reference gate failed; no transfer/learning launches')
    groups=fresh_conditions(root,out.parent)
    # T1 heldout remains fresh; retention intentionally uses the original paired
    # T0 heldout assignments, which were never available to either participant.
    retention=json.loads((pilot/'registration.json').read_text())['conditions']['heldout']
    out.mkdir(parents=True,exist_ok=False)
    reg={'schema':'core-flow-1','registered_at':now(),'source_commit':source,'gpu':gpu,
         'physical_budget':44,'T1_train':groups['train'],'T1_heldout':groups['heldout'],
         'T0_retention':retention,'t0_pilot_results':pilot_result,'pilot_path':str(pilot),
         'place_confirmation_sha256':sha256(confirmation/'place_results.json'),
         'computational_budget':{'calls':12,'input_tokens':400000,'output_tokens':36000},
         'model':json.loads((pilot/'registration.json').read_text())['model'],
         'protocol':'docs/core/CORE_PROTOCOL_20261027.md'}
    save_json(out/'baseline_reference.json',json.loads((pilot/'baseline_reference.json').read_text()))
    save_json(out/'registration.json',reg)
    save_json(out/'status.json',{'status':'RUNNING','at':now()})
    initial={}
    for arm in ('frozen','feedback','search'):
        original=load(pilot/f'{arm}.json')
        save_json(out/f'provenance-T0-{arm}.json',original)
        library=from_reference_skill(ReferenceSkill.from_dict(original['payload']['skill']))
        initial[arm]=freeze(artifact(base,library,original['payload']['participant'],
                                    original['payload']['learning_run_id'],original['payload']['budget_used'],original['payload']['memory'],source),out/f'{arm}-initial.json')
    # Zero-learning transfer is scored before T1 learning but never returned to
    # either updater. Methods get only predeclared T1 training feedback below.
    for arm in ('search','frozen','feedback'):
        evaluate(root,out,source,base,gpu,'transfer-'+arm,initial[arm],'place',groups['heldout'])
    final={}
    for method in ('search','feedback'):
        library=SkillLibrary.from_dict(initial[method]['payload']['skill'])
        best=library
        best_score=-1
        memory=initial[method]['payload']['memory']
        history=[]
        handles={f'train-{i}':c for i,c in enumerate(groups['train'])}
        rng=random.Random(2026102707)
        candidates=[library.to_dict()]
        for variant in range(7):
            candidate=copy.deepcopy(library.to_dict())
            for n in candidate['tasks']['place']['nodes']:
                if n['id']=='approach':
                    n['offset_m']=rng.uniform(.08,.12)
                if n['id']=='close':
                    n['minimum_s']=rng.uniform(.2,.7)
                if n['id']=='release':
                    n['minimum_s']=rng.uniform(.2,.9)
                if n['id']=='lower':
                    n['offset_m']=rng.uniform(.002,.015)
                    n['tolerance']=rng.uniform(.008,.025)
            nodes={n['id']:n for n in candidate['tasks']['place']['nodes']}
            # Public, task-reasonable program templates include structural and
            # guard changes, not only continuous parameters. No feedback or
            # heldout score is used to generate this proposal set.
            if variant in (0,3):
                nodes['close']['next']='lift'  # omit object-follow probe
            if variant in (1,4):
                nodes['transport']['next']='release'  # release from transport height
            if variant in (2,5):
                nodes['lower']['guard']='elapsed'
                nodes['lower']['minimum_s']=.9  # bounded timed descent
            if variant in (3,6):
                candidate['tasks']['place']['max_retries']=2
                nodes['close']['timeout_s']=1.6
            candidates.append(candidate)
        save_json(out/f'{method}-search_distribution.json',candidates)
        model=None
        if method=='feedback':
            model=ParticipantProcess(['codex'],reg['model'],out/'S_model_calls',input_limit=400000,
                                     output_limit=36000,schema=call_schema())
        session=NativeSession(root,out/f'learn-{method}',source,cfg_for(base,'place',8),gpu)
        try:
            session.ready()
            for call in range(12 if model else 8):
                if model:
                    request={'instructions':S_INSTRUCTIONS,'initial_library':initial[method]['payload']['skill'],
                             'inherited_memory':initial[method]['payload']['memory'],
                             'remaining_physical_episodes':8-session.used,'allowed_training_handles':list(handles),
                             'history':compact_history(history)}
                    assert_public(request)
                    answer=model.call(request)
                    if set(answer)!={'tool','library','training_condition_handle','memory'}:
                        raise ValueError('Invalid S participant tool fields')
                    candidate=SkillLibrary.from_dict(answer['library'])
                    candidate.lift.configuration(base)
                    if answer['tool']=='freeze':
                        best,memory=candidate,answer['memory']
                        break
                    if answer['tool']!='run_trial' or answer['training_condition_handle'] not in handles or session.used>=8:
                        raise ValueError('Unauthorized S physical tool')
                    c=handles[answer['training_condition_handle']]
                else:
                    candidate=SkillLibrary.from_dict(candidates[call])
                    c=groups['train'][call%4]
                value={'payload':artifact(base,candidate,reg['model'] if model else 'score-only-template-search-1',
                                          initial[method]['payload']['learning_run_id'],initial[method]['payload']['budget_used']+session.used,memory,source)}
                value['effective_artifact_hash']=digest(value['payload'])
                job=job_for(base,candidate,'place',c,identity_for(value,'place',c,'train',session.used),session.used)
                job['candidate_artifact']=value['payload']
                row=session.trial(job)
                if model:
                    feedback=public_feedback(session.out,row)
                    feedback['place']=row['place']
                    assert_public(feedback)
                    history.append({'tool':'run_trial','candidate_library':candidate.to_dict(),
                                    'training_condition_handle':answer['training_condition_handle'],
                                    'memory':answer['memory'],'feedback':feedback})
                else:
                    score=int(row['success'])
                    if score>best_score:
                        best,best_score=candidate,score
                    history.append({'candidate':candidate.to_dict(),'score':score})
            else:
                if model:
                    raise ValueError('S participant did not freeze within call budget')
        finally:
            session.close()
        save_json(out/f'{method}-history.json',history)
        final[method]=freeze(artifact(base,best,reg['model'] if model else 'score-only-template-search-1',
                                      initial[method]['payload']['learning_run_id'],initial[method]['payload']['budget_used']+session.used,memory,source),out/f'{method}-final.json')
    save_json(out/'all_T1_snapshots_frozen.json',{'at':now(),'hashes':{m:v['effective_artifact_hash'] for m,v in final.items()}})
    for method in ('feedback','search'):
        value=load(out/f'{method}-final.json')
        evaluate(root,out,source,base,gpu,'final-'+method,value,'place',groups['heldout'])
        evaluate(root,out,source,base,gpu,'retention-'+method,value,'lift',retention)
    save_json(out/'status.json',{'status':'COMPLETED','at':now()})
    print(json.dumps(summarize(out),indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--pilot',required=True)
    p.add_argument('--confirmation',required=True)
    p.add_argument('--gpu',type=int,default=2)
    p.add_argument('--report-only',action='store_true')
    a=p.parse_args()
    out=Path(a.output).absolute()
    if a.report_only:
        print(json.dumps(summarize(out),indent=2))
        return
    try:
        run(Path.cwd(),out,Path(a.pilot),Path(a.confirmation),a.gpu)
    except Exception as error:
        if out.exists():
            save_json(out/'status.json',{'status':'FAILED','at':now(),'error':str(error)})
        raise


if __name__=='__main__':
    main()
