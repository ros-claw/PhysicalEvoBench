"""Single preregistered 48-episode development diagnosis, never model learning."""

import argparse
import json
import os
import random
import shutil
from pathlib import Path

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.stability.audit import read, rows
from physicalevobench.stability.study import launch
from physicalevobench.v02.audit import audit_run
from physicalevobench.v02.reference_artifact import ReferenceSkill, digest, load


def register(root, out, reference, gpu):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit source and protocol before reserving physics')
    base = load(reference)
    source, hashes = snapshot_source(root,base['source_commit'])
    excluded = published_seeds(root)
    for path in out.parent.glob('peb-*/registration.json'):
        excluded.update(registered_seed_values(read(path)))
        if read(path).get('phase')=='core-parameter-space-1':
            raise ValueError('The single B1 budget is already reserved')
    rng=random.Random(2026102701)
    conditions=[]
    for i in range(4):
        seed=rng.randrange(2**31)
        while seed in excluded:
            seed=rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id':f'core-b1-dev-{i:02d}','seed':seed,
                           'split':'development','object_mass_kg':(.1 if i<2 else .4)})
    grid=[(a,b) for a in (.08,.10,.12) for b in (.20,.45,.70)]
    rng.shuffle(grid)
    plans=[]
    for i,(clearance,close) in enumerate(grid):
        for name,params in [(f'grid-{i:02d}',(clearance,close))]+(
                [(f'identity-{i//3}',(.10,.20))] if i%3==2 else []):
            skill=ReferenceSkill(digest(base),*params)
            checkpoint=str(Path(os.environ.get('PHYSICALEVOBENCH_CHECKPOINT',
                               '~/models/physicalevobench/franka_lift/model_1999.pt')).expanduser().absolute())
            order=list(conditions)
            rng.shuffle(order)
            plans.append({'name':name,'checkpoint_path':checkpoint,
                          'checkpoint_sha256':base['checkpoint_sha256'],
                          'policy_config_sha256':sha256(Path(checkpoint).parent/'params/agent.yaml'),
                          'mode':'FixedHorizonDiagnostic','execution_layer':'TargetBounded',
                          'reference_controller':'StateBasedReference',
                          'reference_config':skill.configuration(base),'reference_skill':skill.to_dict(),
                          'source_commit':base['source_commit'],'task_version':base['task_version'],
                          'horizon_s':base['horizon_s'],'physical_budget':4,
                          'jobs':[{'episode_id':f'{name}-{c["condition_id"]}','condition':c} for c in order]})
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(reference,out/'baseline_reference.json')
    registration={'schema':'v02-diagnostics-1','phase':'core-parameter-space-1',
                  'source_commit':base['source_commit'],'runtime_source':str(source),
                  'source_sha256':hashes,'launcher_commit':command(['git','rev-parse','HEAD'],cwd=root)['stdout'],
                  'registered_at':now(),'physical_budget':48,'gpu':gpu,'plans':plans,
                  'hard_boundary':{'finger_depth_m':.01,'arm_depth_rad':.1},
                  'target_rate_caps':{'arm_rad_s':1.,'finger_m_s':.04},
                  'protocol':'docs/core/CORE_PROTOCOL_20261027.md',
                  'baseline_reference_file_sha256':sha256(out/'baseline_reference.json')}
    save_json(out/'registration.json',registration)
    return registration


def summarize(out):
    audit=audit_run(out)
    reg=read(out/'registration.json')
    results=[]
    for plan in reg['plans']:
        data=rows(out/plan['name']/'episodes.jsonl')
        results.append({'worker':plan['name'],'skill':plan['reference_skill'],
                        'successes':sum(r['success'] for r in data),'episodes':len(data),
                        'by_condition':{r['condition_id']:r['success'] for r in data},
                        'holding_spans_s':[r['diagnostic']['holding']['maximum_holding_span_s'] for r in data]})
    # This small development experiment cannot establish a learning effect. Even a
    # visible parameter contrast requires a separately frozen confirmatory study.
    counts=[r['successes'] for r in results if r['worker'].startswith('grid')]
    identities=[r['successes'] for r in results if r['worker'].startswith('identity') or
                (r['skill']['approach_clearance_m']==.1 and r['skill']['minimum_close_s']==.2)]
    saturated=all(n==4 for n in counts)
    result={'schema':'core-parameter-space-results-1','audit':audit,'workers':results,
            'grid_success_range':[min(counts),max(counts)],
            'identity_success_range':[min(identities),max(identities)],
            'routing':('P_SMOKE_ONLY_SATURATED' if saturated else 'P_SMOKE_ONLY_UNCONFIRMED'),
            'scope':'48 physical episodes, four independent development conditions, zero learning runs. '
                    'No efficacy inference from timing or post-hoc parameter selection. '
                    'P remains interface smoke unless an independent study is registered; continue to S/T1.'}
    save_json(out/'parameter_space_results.json',result)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--reference')
    p.add_argument('--gpu',type=int,default=2)
    p.add_argument('--report-only',action='store_true')
    a=p.parse_args()
    root,out=Path.cwd(),Path(a.output).absolute()
    if a.report_only:
        print(json.dumps(summarize(out),indent=2))
        return
    if not a.reference:
        p.error('--reference required for execution')
    reg=register(root,out,Path(a.reference),a.gpu)
    complete=[]
    save_json(out/'status.json',{'status':'RUNNING','at':now()})
    try:
        for plan in reg['plans']:
            child=out/plan['name']
            child.mkdir()
            save_json(child/'config.json',plan)
            save_json(child/'worker_reservation.json',{'episodes':4,'reserved_at':now()})
            save_json(child/'gpu_workload.json',{'exclusive':False,'at':now(),
                      'query':command(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv'])})
            launch(root,Path(reg['runtime_source']),child,'physicalevobench.v02.collect',a.gpu)
            complete.extend({'worker':plan['name'],**r} for r in rows(child/'episodes.jsonl'))
            save_json(out/'progress.json',{'completed':len(complete),'last_worker':plan['name'],'at':now()})
        save_json(out/'results.json',{'episodes':complete,'count':len(complete),'learning_updates':0})
        save_json(out/'status.json',{'status':'COMPLETED','episodes':len(complete),'finished_at':now()})
        print(json.dumps(summarize(out),indent=2))
    except Exception as error:
        save_json(out/'status.json',{'status':'INFRA_FAILURE','completed':len(complete),'error':str(error),'at':now()})
        raise


if __name__=='__main__':
    main()
