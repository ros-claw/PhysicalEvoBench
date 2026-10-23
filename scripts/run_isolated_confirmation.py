"""Fresh paired conditions with separate per-policy workers and crossed GPU allocation."""

import argparse
import json
import random
import subprocess
from pathlib import Path

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit confirmation source before registration')
    cfg=json.loads((root/'runs/calibration-ppo-heldout-20261023-001/config.json').read_text())
    ref=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    runtime_source,source_hashes=snapshot_source(root,ref)
    excluded=published_seeds(root)
    for path in (root/'runs').rglob('config.json'):
        payload=json.loads(path.read_text())
        excluded.update(j['condition']['seed'] for j in payload.get('jobs',[]))
        if 'environment_seed' in payload:
            excluded.add(payload['environment_seed'])
    rng=random.Random(202610230801)
    conditions=[]
    for i in range(48):
        seed=rng.randrange(2**31)
        while seed in excluded:
            seed=rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id':f'isolated-202610230801-{i:03d}','split':'heldout_test',
                           'seed':seed,'object_mass_kg':rng.uniform(.8,3.2)})
    out=Path(a.output).absolute()
    out.mkdir(parents=True,exist_ok=False)
    cfg.update(mode='isolated-confirmation',registered_at=now(),source_commit=ref,source_sha256=source_hashes,
               runtime_source_snapshot=str(runtime_source),physical_budget=96,
               jobs=[{'episode_id':f"{c['condition_id']}-{arm}",'condition':c,'policy':arm}
                     for c in conditions for arm in ('original','candidate')])
    save_json(out/'config.json',cfg)
    save_json(out/'registration.json',{'conditions':conditions,'physical_budget':96,
              'source_commit':ref,'registered_at':now(),'learning_updates':0,
              'design':'two blocks of 24 pairs; separate per-policy workers; original/candidate GPU allocation crossed',
              'primary_summary':'48 paired success differences, exact one-sided p and conditional interval; report alongside initial study',
              'caution':'follow-up motivated by post-hoc order stratification; one learned model, no independent training replication'})
    plans=[]
    for block in range(2):
        for arm in ('original','candidate'):
            gpu=block if arm=='original' else 1-block
            child=out/f'block-{block}-{arm}'
            child.mkdir()
            jobs=[{'episode_id':f"{c['condition_id']}-{arm}",'condition':c,'policy':arm}
                  for c in conditions[24*block:24*(block+1)]]
            save_json(child/'config.json',{**cfg,'jobs':jobs,'physical_budget':24,'block':block,'gpu':gpu})
            plans.append((child,gpu))
    arena=root/'external/IsaacLab-Arena'
    processes=[]
    for child,gpu in plans:
        argv=[str(arena_python_path({},arena)),'-m','physicalevobench.calibration.collect','--run-dir',str(child)]
        environment=runtime_environment(arena,gpu)
        environment['PYTHONPATH']=str(runtime_source)
        stream=(child/'console.log').open('w')
        save_json(child/'launch.json',{'argv':argv,'gpu':gpu,'runtime_source_commit':ref})
        process=subprocess.Popen(argv,cwd=arena,env=environment,stdout=stream,stderr=subprocess.STDOUT)
        processes.append((child,process,stream))
    for child,process,stream in processes:
        code=process.wait(timeout=1800)
        stream.close()
        save_json(child/'process.json',{'returncode':code,'finished_at':now()})
    failed=any(process.returncode for _,process,_ in processes)
    save_json(out/'status.json',{'status':'INFRA_FAILURE' if failed else 'COMPLETED',
              'physical_episodes':sum(len((child/'episodes.jsonl').read_text().splitlines())
                  if (child/'episodes.jsonl').exists() else 0 for child,_,_ in processes)})
    return int(failed)


if __name__=='__main__':
    main()
