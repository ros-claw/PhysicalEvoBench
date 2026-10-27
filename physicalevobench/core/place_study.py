"""Bounded development and independent reference confirmation for a new task."""

import argparse
import json
import random
import shutil
import time
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.pilot import fresh_conditions, worker_config
from physicalevobench.core.program import initial_program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import digest
from physicalevobench.v02.reference_artifact import load as load_reference


def run(root,out,reference,gpu,after,confirmation=None):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit T1 implementation before reservation')
    base=load_reference(reference)
    commit=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    groups=fresh_conditions(root,out.parent)
    rng=random.Random(2026102706 if confirmation else 2026102705)
    excluded={c['seed'] for cs in groups.values() for c in cs}
    # Additional fresh seeds are drawn from a different deterministic stream and
    # checked against all previous registered sources, including nested conditions.
    from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
    excluded.update(published_seeds(root))
    for path in out.parent.glob('peb-*/registration.json'):
        excluded.update(registered_seed_values(json.loads(path.read_text())))
    conditions=[]
    for i in range(6 if confirmation else 4):
        seed=rng.randrange(2**31)
        while seed in excluded:
            seed=rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id':f'core-place-{"confirmation" if confirmation else "dev"}-{i:02d}',
                           'split':'confirmation' if confirmation else 'development',
                           'seed':seed,'object_mass_kg':.1 if i<(3 if confirmation else 2) else .4})
    program=initial_program(True)
    cfg=worker_config(base,12 if confirmation else 8)
    cfg.update(core_task='place',task_version='core-place-h20-v2-dev',horizon_s=20.)
    if confirmation:
        prior=json.loads((confirmation/'place_results.json').read_text())
        if not prior['development_qualified']:
            raise ValueError('No feasible frozen T1 reference; confirmation not authorized')
        frozen=json.loads((confirmation/'frozen_place_reference.json').read_text())
        if digest(frozen['payload'])!=frozen['sha256']:
            raise ValueError('T1 reference hash changed')
        program=initial_program(True).from_dict(frozen['payload']['program'])
        commit=frozen['payload']['source_commit']
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(reference,out/'baseline_reference.json')
    if confirmation:
        shutil.copyfile(confirmation/'frozen_place_reference.json',out/'frozen_place_reference.json')
    jobs=[]
    for i,c in enumerate(conditions):
        pair=[False,True] if i%2==0 else [True,False]
        for force_open in pair:
            identity={'learning_run_id':'not_applicable','budget_used':0,'checkpoint_index':0,
                      'effective_artifact_hash':digest({'source_commit':commit,'program':program.to_dict(),
                                                       'reference_config':base['reference_config'],
                                                       'task':cfg['task_version'],'force_open':force_open}),
                      'task_id':cfg['task_version'],'split_id':c['split'],'condition_id':c['condition_id'],
                      'physical_replay_id':f'place-{len(jobs)}','execution_profile':'TargetBounded-reference-v2-1'}
            jobs.append({'episode_id':f'place-{len(jobs):03d}','condition':c,
                         'reference_config':base['reference_config'],'program':program.to_dict(),
                         'force_open':force_open,'identity':identity})
    save_json(out/'registration.json',{'schema':'core-place-study-1','registered_at':now(),
              'phase':'confirmation' if confirmation else 'development','source_commit':commit,
              'physical_budget':len(jobs),'jobs':jobs,'cfg':cfg,'gpu':gpu,'after':str(after),
              'protocol':'docs/core/CORE_PROTOCOL_20261027.md'})
    save_json(out/'status.json',{'status':'QUEUED','at':now()})
    if after:
        while not (after/'status.json').exists() or json.loads((after/'status.json').read_text())['status'] in ('RUNNING','QUEUED'):
            time.sleep(5)
    # T1 reference feasibility is independent of the algorithm winning its pilot.
    # A failed learning process cannot be counted as a completed B2/B3.
    save_json(out/'status.json',{'status':'RUNNING','at':now()})
    session=NativeSession(root,out/'native',commit,cfg,gpu)
    try:
        session.ready()
        for job in jobs:
            session.trial(job)
    finally:
        session.close()
    data=audit_session(out/'native')
    positive=[r for i,r in enumerate(data) if not jobs[i]['force_open']]
    negative=[r for i,r in enumerate(data) if jobs[i]['force_open']]
    surface={}
    for mass in (.1,.4):
        group=[r for i,r in enumerate(data) if not jobs[i]['force_open'] and jobs[i]['condition']['object_mass_kg']==mass]
        surface[str(mass)]={'successes':sum(r['success'] for r in group),'episodes':len(group)}
    safe=not any(r['diagnostic']['hard_boundary_terminated'] for r in data)
    qualified=(sum(r['success'] for r in positive)>=3 and not any(r['success'] for r in negative) and safe)
    gate=(all(v['successes']>=2 for v in surface.values()) and not any(r['success'] for r in negative) and safe)
    result={'schema':'core-place-results-1','audit':'PASS','phase':'confirmation' if confirmation else 'development',
            'positive':{'successes':sum(r['success'] for r in positive),'episodes':len(positive)},
            'negative':{'successes':sum(r['success'] for r in negative),'episodes':len(negative)},
            'by_mass':surface,'development_qualified':qualified if not confirmation else None,
            'independent_gate_passed':gate if confirmation else None,
            'registered_violation_episodes':sum(r['diagnostic']['first_violation'] is not None for r in data),
            'episodes':[{'id':r['episode_id'],'success':r['success'],'place':r['place'],'steps':r['steps']} for r in data],
            'scope':'New task feasibility/reference only; not participant learning.'}
    save_json(out/'place_results.json',result)
    if not confirmation and qualified:
        frozen={'source_commit':commit,'program':program.to_dict(),'configuration':cfg,
                'scoring':'core-place-score-1','task':'core-place-h20-v2-dev'}
        save_json(out/'frozen_place_reference.json',{'payload':frozen,'sha256':digest(frozen)})
    save_json(out/'status.json',{'status':'COMPLETED','at':now(),'episodes':len(data)})
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--reference',required=True)
    p.add_argument('--gpu',type=int,default=2)
    p.add_argument('--after')
    p.add_argument('--confirmation-development')
    a=p.parse_args()
    out=Path(a.output).absolute()
    try:
        run(Path.cwd(),out,Path(a.reference),a.gpu,Path(a.after) if a.after else None,
            Path(a.confirmation_development) if a.confirmation_development else None)
    except Exception as error:
        if out.exists():
            save_json(out/'status.json',{'status':'FAILED','error':str(error),'at':now()})
        raise


if __name__=='__main__':
    main()
