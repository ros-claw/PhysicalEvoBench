"""The sole four-positive T1 feasibility correction, within original dev cap12."""

import argparse
import json
import random
import time
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.pilot import worker_config
from physicalevobench.core.program import Program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.stability.audit import read, rows
from physicalevobench.v02.reference_artifact import digest
from physicalevobench.v02.reference_artifact import load as load_reference


def run(root,out,parent,after,gpu):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit sole T1 correction before registration')
    previous=read(parent/'registration.json')
    observed=rows(parent/'native/episodes.jsonl')
    failed=[r for i,r in enumerate(observed) if not previous['jobs'][i]['force_open'] and not r['success']]
    # Once two of four positives fail, the maximum possible final success is2/4.
    # Register the single correction without waiting to choose a favorable last result.
    if len(failed)<2:
        raise ValueError('Initial T1 development must conclusively fail the3/4 gate')
    reserved=0
    excluded=published_seeds(root)
    for path in out.parent.glob('peb-*/registration.json'):
        value=read(path)
        excluded.update(registered_seed_values(value))
        if value.get('schema')=='core-place-study-1' and value['phase']=='development':
            if read(path.parent/'status.json')['status']!='CANCELLED_BEFORE_LAUNCH':
                reserved+=value['physical_budget']
    if reserved+4>12:
        raise ValueError('T1 development cap12 includes the sole correction; no further candidates')
    base=load_reference(parent/'baseline_reference.json')
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    program=Program.from_dict(previous['jobs'][0]['program']).to_dict()
    for n in program['nodes']:
        if n['id'] in ('release','retreat','done'):
            n['mode']='hold'  # Keep the same bounded feedback active while open.
        if n['id']=='release':
            n['minimum_s']=.70  # Do not retreat before the bounded fingers open.
    Program.from_dict(program)
    rng=random.Random(2026102708)
    conditions=[]
    for i in range(4):
        seed=rng.randrange(2**31)
        while seed in excluded:
            seed=rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id':f'core-place-correction-{i:02d}','seed':seed,
                           'split':'development','object_mass_kg':.1 if i<2 else .4})
    cfg=worker_config(base,4)
    cfg.update(core_task='place',horizon_s=20.,task_version='core-place-h20-v2-dev')
    identity_hash=digest({'source_commit':source,'program':program,'reference_config':base['reference_config'],
                          'task':cfg['task_version'],'force_open':False})
    jobs=[]
    for i,c in enumerate(conditions):
        identity={'learning_run_id':'not_applicable','budget_used':0,'checkpoint_index':0,
                  'effective_artifact_hash':identity_hash,'task_id':cfg['task_version'],'split_id':'development',
                  'condition_id':c['condition_id'],'physical_replay_id':f'correction-{i}',
                  'execution_profile':'TargetBounded-reference-v2-1'}
        jobs.append({'episode_id':f'correction-{i:03d}','condition':c,'program':program,
                     'reference_config':base['reference_config'],'force_open':False,'identity':identity})
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'baseline_reference.json',read(parent/'baseline_reference.json'))
    save_json(out/'registration.json',{'schema':'core-place-study-1','registered_at':now(),'phase':'development',
              'development_variant':'sole_release_stabilization_correction','source_commit':source,
              'physical_budget':4,'jobs':jobs,'cfg':cfg,'gpu':gpu,'after':str(after),
              'correction_parent':{'registration_sha256':sha256(parent/'registration.json'),
                                   'observed_failed_positives':[r['episode_id'] for r in failed]},
              'protocol':'docs/core/CORE_PROTOCOL_20261027.md',
              'hypothesis':'Maintain bounded joint feedback through opening and wait0.70s before retreat; prior reset/early retreat may displace cube. Not a unique-cause claim.'})
    save_json(out/'status.json',{'status':'QUEUED','at':now()})
    while read(after/'status.json')['status'] in ('RUNNING','QUEUED'):
        time.sleep(5)
    if any(not (p.parent/'process.json').exists() for p in after.rglob('launch.json')):
        raise ValueError('Earlier native process has not exited')
    save_json(out/'status.json',{'status':'RUNNING','at':now()})
    session=NativeSession(root,out/'native',source,cfg,gpu)
    try:
        session.ready()
        for job in jobs:
            session.trial(job)
    finally:
        session.close()
    data=audit_session(out/'native')
    successful=sum(r['success'] for r in data)
    hard=any(r['diagnostic']['hard_boundary_terminated'] for r in data)
    qualified=successful>=3 and not hard
    result={'schema':'core-place-results-1','audit':'PASS','phase':'sole_development_correction',
            'positive':{'successes':successful,'episodes':4},'negative':{'successes':0,'episodes':0},
            'development_qualified':qualified,'independent_gate_passed':None,
            'registered_violation_episodes':sum(r['diagnostic']['first_violation'] is not None for r in data),
            'episodes':[{'id':r['episode_id'],'success':r['success'],'place':r['place'],'steps':r['steps']} for r in data],
            'scope':'Four new positive conditions, original8 retained; development cap12 exhausted. '
                    'No new negative calibration here; frozen independent confirmation must include6 forced-open.'}
    save_json(out/'place_results.json',result)
    if qualified:
        frozen={'source_commit':source,'program':program,'configuration':cfg,
                'scoring':'core-place-score-1','task':cfg['task_version']}
        save_json(out/'frozen_place_reference.json',{'payload':frozen,'sha256':digest(frozen)})
    save_json(out/'status.json',{'status':'COMPLETED','at':now(),'episodes':len(data)})
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--development',required=True)
    p.add_argument('--after',required=True)
    p.add_argument('--gpu',type=int,default=2)
    a=p.parse_args()
    out=Path(a.output).absolute()
    try:
        run(Path.cwd(),out,Path(a.development),Path(a.after),a.gpu)
    except Exception as error:
        if out.exists():
            save_json(out/'status.json',{'status':'FAILED','at':now(),'error':str(error)})
        raise


if __name__=='__main__':
    main()
