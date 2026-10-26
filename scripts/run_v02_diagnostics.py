"""Preregister small diagnostic budgets; use existing immutable-source launcher."""

import argparse
import json
import random
import time
from pathlib import Path

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds
from physicalevobench.stability.audit import read
from physicalevobench.stability.study import launch
from physicalevobench.v02.audit import episode_metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['smoke', 'representatives', 'repeatability', 'reachability'], required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--gpu', type=int, default=0)
    p.add_argument('--checkpoint', default='/home/dell/models/physicalevobench/franka_lift/model_1999.pt')
    p.add_argument('--history', default='runs/v02-history-20261026/history_diagnosis.json')
    p.add_argument('--smoke', help='Completed instrumented smoke, required after integration')
    p.add_argument('--after', help='Queue behind a registered diagnostic run; never overlap native workers')
    a = p.parse_args()
    root, out = Path.cwd(), Path(a.output).absolute()
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit v02 source and protocol before physical registration')
    if a.phase != 'smoke' and (not a.smoke or read(Path(a.smoke)/'status.json')['status'] != 'COMPLETED'):
        raise ValueError('Instrumented smoke must complete first')
    ref = command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    source, hashes = snapshot_source(root,ref)
    checkpoint = str(Path(a.checkpoint).absolute())
    original = sha256(checkpoint)
    if original != 'babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa':
        raise ValueError('Original checkpoint changed')
    plans=[]

    def add(name, model, conditions, mode='LegacyInstant', layer='TargetBounded'):
        plans.append({'name':name, 'checkpoint_path':model, 'checkpoint_sha256':sha256(model),
                      'mode':mode, 'execution_layer':layer,
                      'physical_budget':len(conditions), 'jobs':[
                          {'episode_id':f"{name}-{i:03d}",'condition':c} for i,c in enumerate(conditions)]})

    if a.phase == 'smoke':
        condition={'condition_id':'v02-nominal-smoke','split':'diagnostic','seed':2026102601,'object_mass_kg':.1}
        for mode in ('LegacyInstant','FixedHorizonDiagnostic'):
            add(mode,checkpoint,[condition],mode)
    elif a.phase == 'representatives':
        representatives=read(root/a.history)['representatives']
        seen=set()
        for i,item in enumerate(representatives):
            if 'episode_id' not in item:
                continue
            identity=(item['checkpoint_sha256'],item['condition']['condition_id'])
            if identity in seen:
                continue
            seen.add(identity)
            for layer in ('NumericalOnly','TargetBounded'):
                add(f"sample-{i:02d}-{layer}",item['checkpoint_path'],[item['condition']],layer=layer)
    elif a.phase == 'repeatability':
        excluded=published_seeds(root)
        rng=random.Random(2026102602)
        conditions=[]
        for i in range(16):
            seed=rng.randrange(2**31)
            while seed in excluded:
                seed=rng.randrange(2**31)
            excluded.add(seed)
            conditions.append({'condition_id':f'v02-repetition-{i:02d}','split':'development',
                               'seed':seed,'object_mass_kg':[.1,.4,.8,1.6][i//4]})
        add('reuse-reset',checkpoint,[c for _ in range(3) for c in conditions])
        for repeat in range(3):
            for i,c in enumerate(conditions):
                add(f'fresh-r{repeat}-{i:02d}',checkpoint,[c])
    else:
        excluded = published_seeds(root)
        rng = random.Random(2026102603)
        conditions = []
        for i in range(12):
            seed = rng.randrange(2**31)
            while seed in excluded:
                seed = rng.randrange(2**31)
            excluded.add(seed)
            conditions.append({'condition_id': f'v02-reachability-{i:02d}', 'split': 'development',
                               'seed': seed, 'object_mass_kg': [.1,.4,.8,1.6][i//3]})
        for controller in ('Original', 'GeometryExpert', 'OpenGripper'):
            add(controller, checkpoint, conditions, mode='FixedHorizonDiagnostic')
            plans[-1]['reference_controller'] = controller
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'registration.json',{'schema':'v02-diagnostics-1','phase':a.phase,'source_commit':ref,
              'source_sha256':hashes,'runtime_source':str(source),'registered_at':now(),
              'gpu':a.gpu,'physical_budget':sum(p['physical_budget'] for p in plans),
              'hard_boundary':{'finger_depth_m':.01,'arm_depth_rad':.1},
              'target_rate_caps':{'arm_rad_s':1.,'finger_m_s':.04},
              'plans':plans,'score_role':'development diagnosis only; no learning or heldout efficacy score',
              'after': None if not a.after else {'path': str(Path(a.after).absolute()),
                                               'registration_sha256': sha256(Path(a.after)/'registration.json')}})
    completed=[]
    try:
        if a.after:
            predecessor = Path(a.after)
            save_json(out/'status.json', {'status': 'QUEUED', 'after': str(predecessor), 'at': now()})
            while not (predecessor/'status.json').exists():
                time.sleep(5)
            while read(predecessor/'status.json')['status'] == 'QUEUED':
                time.sleep(5)
            if read(predecessor/'status.json')['status'] != 'COMPLETED':
                raise ValueError('Prerequisite diagnostic did not complete; no dependent physics launched')
        save_json(out/'status.json', {'status': 'RUNNING', 'at': now()})
        for plan in plans:
            child=out/plan['name']
            child.mkdir()
            save_json(child/'config.json',plan)
            save_json(child/'worker_reservation.json',{'episodes':plan['physical_budget'],'reserved_at':now()})
            load=command(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader'])
            save_json(child/'gpu_workload.json',{'at':now(),'query':load,'exclusive':False})
            launch(root,source,child,'physicalevobench.v02.collect',a.gpu)
            rows=[json.loads(line) for line in (child/'episodes.jsonl').read_text().splitlines()]
            if len(rows)!=plan['physical_budget']:
                raise ValueError('Missing diagnostic episodes')
            for row,job in zip(rows,plan['jobs'],strict=True):
                directory=child/'episodes'/row['episode_id']
                if read(directory/'initial_state.json')['condition'] != job['condition']:
                    raise ValueError('Diagnostic condition mismatch')
                if episode_metrics(directory,child/'control_semantics.json') != row['diagnostic']:
                    raise ValueError('Diagnostic metrics mismatch')
            completed.extend({'worker':plan['name'],**row} for row in rows)
            save_json(out/'progress.json',{'completed_episodes':len(completed),'budget':sum(p['physical_budget'] for p in plans)})
        save_json(out/'results.json',{'episodes':completed,'count':len(completed),'learning_updates':0})
        save_json(out/'status.json',{'status':'COMPLETED','episodes':len(completed),'finished_at':now()})
        print({'status':'COMPLETED','episodes':len(completed)})
    except Exception as error:
        physical = [json.loads(line) for path in out.glob('*/episodes/*/upstream.jsonl')
                    for line in path.read_text().splitlines() if line.strip()]
        save_json(out/'status.json',{'status':'INFRA_FAILURE','audited_episodes':len(completed),
                  'completed_physics_episodes':sum(row.get('episode_length',0)>0 for row in physical),
                  'error':str(error),'at':now()})
        raise


if __name__ == '__main__':
    main()
