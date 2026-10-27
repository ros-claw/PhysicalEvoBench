"""Offline recomputation: physical traces, tool budgets and artifact causality."""

import argparse
import json
import math
from pathlib import Path

from physicalevobench.core.artifact import load
from physicalevobench.core.metrics import compare, place_metrics
from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read, rows
from physicalevobench.v02.audit import episode_metrics, records
from physicalevobench.v02.reference import BoundedJointIntegral, ReferenceConfig, ReferenceFSM
from physicalevobench.v02.reference_artifact import ReferenceSkill, digest
from physicalevobench.v02.reference_artifact import load as load_reference


PRIVATE_KEYS={'seed','object_mass_kg','mass_readback_kg','inertia_readback','split','split_id',
              'condition_id','heldout','test_results','evaluator_config','checkpoint_path'}


def assert_public(value):
    if isinstance(value,dict):
        if set(value)&PRIVATE_KEYS:
            raise ValueError('Private evaluator field entered participant payload')
        for v in value.values():
            assert_public(v)
    elif isinstance(value,list):
        for v in value:
            assert_public(v)


def force_norm(value):
    if isinstance(value[0],list):
        return max(force_norm(v) for v in value)
    return math.sqrt(sum(v*v for v in value))


def audit_session(worker):
    worker=Path(worker)
    cfg=read(worker/'config.json')
    if read(worker/'process.json')['returncode']!=0:
        raise ValueError('Unsuccessful native process')
    if sha256(worker/'policy_config.yaml')!=cfg['policy_config_sha256']:
        raise ValueError('Inference context changed')
    meta=read(worker/'control_semantics.json')
    if (meta['target_rate_caps']!={'arm_rad_s':1.,'finger_m_s':.04} or
            meta['hard_boundary']!={'finger_depth_m':.01,'arm_depth_rad':.1} or
            meta['execution_layer']!='TargetBounded'):
        raise ValueError('Shared execution constraints changed')
    data=rows(worker/'episodes.jsonl')
    if len(data)>cfg['physical_budget'] or read(worker/'server_receipt.json')['completed']!=len(data):
        raise ValueError('Physical ledger or budget mismatch')
    if len(list((worker/'requests').glob('*.json')))!=len(data):
        raise ValueError('Missing or uncompleted reserved physical attempts')
    for i,row in enumerate(data):
        job=read(worker/'requests'/f'{i:03d}.json')
        if read(worker/'reservations'/f'{i:03d}.json')['job']!=job:
            raise ValueError('Physical request changed after reservation')
        episode=worker/'episodes'/row['episode_id']
        if read(episode/'episode.json')!=row or row['core_identity']!=job['identity']:
            raise ValueError('Episode/artifact identity changed')
        if job.get('candidate_artifact'):
            if digest(job['candidate_artifact'])!=job['identity']['effective_artifact_hash']:
                raise ValueError('Effective training artifact identity changed')
        if read(episode/'initial_state.json')['condition']!=job['condition']:
            raise ValueError('Executed condition differs from reservation')
        if abs(read(episode/'initial_state.json')['mass_readback_kg'][0][0]-job['condition']['object_mass_kg'])>1e-5:
            raise ValueError('Physical mass mismatch')
        if episode_metrics(episode,worker/'control_semantics.json')!=row['diagnostic']:
            raise ValueError('Physical outcome changed')
        frames=records(episode/'physics.jsonl.gz')
        if cfg.get('core_task')=='place':
            score=place_metrics(read(episode/'initial_capture.json'),frames)
            if score!=row['place'] or score['success']!=row['success']:
                raise ValueError('Object/release scoring mismatch')
        elif row['success']!=row['diagnostic']['holding']['stable_success']:
            raise ValueError('Task outcome differs from physical criterion')
        trace=records(worker/row['trace_artifact'])
        if sha256(worker/row['trace_artifact'])!=row['trace_sha256'] or len(trace)!=row['steps']:
            raise ValueError('Trace digest or coverage changed')
        controls=records(episode/'controls.jsonl.gz')
        upstream=[r for r in rows(episode/'upstream.jsonl') if r.get('episode_length',0)>0]
        if len(upstream)!=1 or upstream[0]['episode_length']!=row['steps']:
            raise ValueError('Upstream physical completion missing')
        config=ReferenceConfig(**job['reference_config'])
        if job.get('program'):
            from physicalevobench.core.program import Program, ProgramFSM
            fsm=ProgramFSM(Program.from_dict(job['program']))
        else:
            fsm=ReferenceFSM(config)
        integral=BoundedJointIntegral(config.joint_integral_gain_s,config.joint_integral_limit_rad)
        initial=read(episode/'initial_capture.json')
        for s,c in zip(trace,controls,strict=True):
            d=s['policy_diagnostics']
            public=d['public']
            assert_public(public)
            decision=fsm.update(public,meta['control_dt'])
            if decision!=d['decision']:
                raise ValueError('Actual skill command differs from public-state program')
            bias=integral.update(d['joint_error_feedback_rad'],meta['control_dt'],decision['phase'] in ('lift','hold'))
            if bias!=d['bounded_joint_integral_rad']:
                raise ValueError('Fixed integral feedback changed')
            if public['object_position']!=s['object_position'][0] or public['ee_position']!=s['ee_position'][0][0]:
                raise ValueError('Program observations differ from physical state')
            previous=initial if s['step']==0 else frames[s['step']*meta['decimation']-1]
            if any(not math.isclose(force_norm(previous['contacts'][side]['cube_force_matrix_w']['value']),
                                    public['cube_contact_force'][j],rel_tol=1e-6,abs_tol=1e-4)
                   for j,side in enumerate(('left','right'))):
                raise ValueError('Contact guard is not physical normal force')
            if (c['network_proposal']!=s['raw_action'] or c['accepted_raw_action']!=s['applied_action'] or
                    s['applied_action'][0]!=[max(-1000.,min(1000.,x)) for x in s['raw_action'][0]]):
                raise ValueError('Proposed versus applied action mismatch')
            grip=s['raw_action'][0][meta['action_terms']['gripper_action']['mapping']['start']]
            if grip!=(1. if job.get('force_open') or decision['gripper']=='open' else -1.):
                raise ValueError('Program gripper primitive ignored')
    return data


def audit_pilot(out):
    out=Path(out)
    reg=read(out/'registration.json')
    base=load_reference(out/'baseline_reference.json')
    if sha256(out/'baseline_reference.json')!=reg['baseline_reference_sha256']:
        raise ValueError('Initial ability changed')
    train,test=reg['conditions']['train'],reg['conditions']['heldout']
    if {c['seed'] for c in train}&{c['seed'] for c in test}:
        raise ValueError('Train/test seed overlap')
    artifacts={arm:load(out/f'{arm}.json') for arm in reg['evaluation_order']}
    frozen=read(out/'all_snapshots_frozen.json')
    if frozen['artifacts']!={k:v['effective_artifact_hash'] for k,v in artifacts.items()}:
        raise ValueError('Post-freeze artifact mutation')
    total,steps,samples=0,0,0
    test_scores={}
    initials={}
    train_counts={}
    for name in ['train-feedback','train-search']+[f'test-{a}' for a in reg['evaluation_order']]:
        worker=out/name
        data=audit_session(worker)
        total+=len(data)
        steps+=sum(r['steps'] for r in data)
        samples+=sum(r['diagnostic']['physics_samples'] for r in data)
        if name.startswith('test-'):
            arm=name[5:]
            if read(worker/'launch.json')['started_at']<=frozen['at']:
                raise ValueError('Heldout execution started before all snapshots froze')
            if {r['condition_id'] for r in data}!={c['condition_id'] for c in test}:
                raise ValueError('Missing paired heldout conditions')
            artifact=artifacts[arm]
            skill=ReferenceSkill.from_dict(artifact['payload']['skill'])
            for i,r in enumerate(data):
                job=read(worker/'requests'/f'{i:03d}.json')
                c=next(c for c in test if c['condition_id']==r['condition_id'])
                if (job['condition']!=c or job['reference_config']!=skill.configuration(base) or
                        r['core_identity']['effective_artifact_hash']!=artifact['effective_artifact_hash']):
                    raise ValueError('Heldout artifact or condition changed')
                init=read(worker/'episodes'/r['episode_id']/'initial_capture.json')
                key=r['condition_id']
                if key in initials:
                    for field in ('joint_position','object_position','target_command'):
                        # Actual reset equality is measured, not inferred from seed.
                        def flat(v):
                            return [x for a in v for x in (flat(a) if isinstance(a,list) else [a])]
                        if max(abs(a-b) for a,b in zip(flat(initials[key][field]),flat(init[field]),strict=True))>1e-6:
                            raise ValueError('Paired initial physical state mismatch')
                else:
                    initials[key]=init
            test_scores[arm]={r['condition_id']:r['success'] for r in data}
        else:
            train_counts[name]=len(data)
            for i,r in enumerate(data):
                job=read(worker/'requests'/f'{i:03d}.json')
                if job['condition'] not in train:
                    raise ValueError('Unauthorized training condition')
    for request in (out/'model_calls').glob('call-*/request.json'):
        assert_public(read(request))
    usages=[read(p) for p in sorted((out/'model_calls').glob('call-*/usage.json'))]
    usage={'calls':len(usages),'input_tokens':sum(u['input_tokens'] for u in usages),
           'output_tokens':sum(u['output_tokens'] for u in usages)}
    if usage!=read(out/'model_calls/budget.json') or any(usage[k]>reg['computational_budget'][k] for k in usage):
        raise ValueError('Reported model computation or limits differ')
    if total>reg['physical_budget'] or train_counts['train-feedback']>8 or train_counts['train-search']!=8:
        raise ValueError('Physical study budget exceeded')
    tools=[read(p) for p in sorted(out.glob('feedback-tool-*.json'))]
    if tools[-1]['tool']!='freeze' or sum(t['tool']=='run_trial' for t in tools)!=train_counts['train-feedback']:
        raise ValueError('Model tool provenance incomplete')
    retained=artifacts['feedback']['payload']
    if (retained['skill']!=ReferenceSkill(digest(base),tools[-1]['approach_clearance_m'],tools[-1]['minimum_close_s']).to_dict()
            or retained['memory']!=tools[-1]['memory']):
        raise ValueError('Frozen experience was not chosen by actual participant')
    result={'schema':'core-pilot-results-1','audit':'PASS','episodes':total,'control_steps':steps,
            'physics_samples':samples,'independent_feedback_learning_runs':1,
            'independent_search_learning_runs':1,'training_episodes':train_counts,'model_cost':usage,
            'arms':{a:{'successes':sum(v.values()),'episodes':len(v),'scores':v,
                       'artifact_hash':artifacts[a]['effective_artifact_hash'],
                       'skill_hash':ReferenceSkill.from_dict(artifacts[a]['payload']['skill']).sha256}
                    for a,v in test_scores.items()},
            'feedback_vs_initial':compare(test_scores['frozen'],test_scores['feedback']),
            'search_vs_initial':compare(test_scores['frozen'],test_scores['search']),
            'artifact_contribution':compare(test_scores['ablation'],test_scores['feedback']),
            'scope':'P interface pilot; one learning run/method and four paired conditions; no program evolution, cross-task or stable efficacy claim.'}
    save_json(out/'pilot_results.json',result)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    a=p.parse_args()
    print(json.dumps(audit_pilot(Path(a.run_dir)),indent=2))


if __name__=='__main__':
    main()
