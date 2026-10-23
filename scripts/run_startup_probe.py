"""Bounded targeted reproduction of observed first-episode free falls on two GPUs."""

import argparse
import json
import subprocess
from pathlib import Path

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.doctor import command, save_json
from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.evaluation.confirmation import now


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit source before targeted probe')
    out=Path(a.output).absolute()
    out.mkdir(parents=True,exist_ok=False)
    ref=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    runtime_source,source_hashes=snapshot_source(root,ref)
    plans=[]
    for i,name in enumerate(('calibration-expert-v3-pilot-20261023-001','calibration-expert-test-20261023-001')):
        source=root/'runs'/name/'config.json'
        cfg=json.loads(source.read_text())
        condition={**cfg['jobs'][0]['condition'],'split':'diagnostic'}
        for gpu in (0,1):
            child=out/f'condition-{i}-gpu-{gpu}'
            child.mkdir()
            jobs=[{'episode_id':f'repeat-{j}','policy':'original','condition':condition} for j in range(3)]
            cfg.update(mode='replay',jobs=jobs,physical_budget=3,source_commit=ref,runtime_source_snapshot=str(runtime_source),source_sha256=source_hashes,
                       registered_at=now(),targeted_condition_source=str(source))
            save_json(child/'config.json',cfg)
            plans.append((child,gpu))
    save_json(out/'registration.json',{'physical_budget':12,'workers':4,'registered_at':now(),
              'hypothesis':'first-episode support/contact readiness versus repeat and GPU',
              'scope':'targeted reuse of two observed anomalous conditions; not an anomaly-rate estimate'})
    arena=root/'external/IsaacLab-Arena'
    processes=[]
    for child,gpu in plans:
        argv=[str(arena_python_path({},arena)),'-m','physicalevobench.calibration.collect','--run-dir',str(child)]
        log=(child/'console.log').open('w')
        save_json(child/'launch.json',{'argv':argv,'gpu':gpu})
        native_environment=runtime_environment(arena,gpu)
        native_environment['PYTHONPATH']=str(runtime_source)
        process=subprocess.Popen(argv,cwd=arena,env=native_environment,stdout=log,stderr=subprocess.STDOUT)
        processes.append((child,process,log))
    for child,process,log in processes:
        code=process.wait(timeout=900)
        log.close()
        save_json(child/'process.json',{'returncode':code,'finished_at':now()})
    failed=any(process.returncode for _,process,_ in processes)
    save_json(out/'status.json',{'status':'INFRA_FAILURE' if failed else 'COMPLETED','physical_episodes':
              sum(len((child/'episodes.jsonl').read_text().splitlines()) if (child/'episodes.jsonl').exists() else 0 for child,_,_ in processes)})
    return int(failed)


if __name__=='__main__':
    raise SystemExit(main())
