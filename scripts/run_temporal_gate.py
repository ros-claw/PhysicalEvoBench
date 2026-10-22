"""Register the selected training candidate and a new independent validation gate."""

import argparse
import random
import subprocess
from pathlib import Path

import yaml

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.confirmation_audit import load
from physicalevobench.evaluation.seed_registry import published_seeds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exploration', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--gpu', type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit validation gate code before registration')
    exploration = Path(args.exploration).absolute()
    if load(exploration/'audit.json')['status']!='PASS':
        raise ValueError('Audit training evidence before selecting validation candidate')
    selection=load(exploration/'training_selection.json')
    if selection['selected']['trial']=='original':
        raise ValueError('No nonidentity training-selected candidate; do not claim adaptation')
    cfg=yaml.safe_load((root/'configs/confirmation.yaml').read_text())
    arena=(root/cfg['arena_path']).resolve()
    excluded=published_seeds(root)
    excluded.update(c['seed'] for c in load(exploration/'registration.json')['conditions'])
    rng=random.Random(202610221201)
    conditions=[]
    for i in range(16):
        seed=rng.randrange(2**31)
        while seed in excluded:
            seed=rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id':f'temporal-gate-validation-{i:03d}',
                           'split':'validation','seed':seed,'object_mass_kg':rng.uniform(.8,3.2)})
    output=Path(args.output).absolute()
    output.mkdir(parents=True,exist_ok=False)
    cfg.update(arena_path=str(arena), selected_skill=selection['selected']['skill'], conditions=conditions,
               registration_time=now(), source_commit=command(['git','rev-parse','HEAD'],cwd=root),
               training_selection_sha256=sha256(exploration/'training_selection.json'),
               gate_rule='Strictly more successes and no increase in total joint-limit samples',
               physical_budget=32, heldout_test_budget=0)
    save_json(output/'config.json',cfg)
    launch=[str(arena_python_path(cfg,arena)),'-m','physicalevobench.evaluation.temporal_gate',
            '--run-dir',str(output)]
    save_json(output/'launch.json',{'command':launch,'physical_gpu':args.gpu})
    with (output/'console.log').open('w') as log:
        result=subprocess.run(launch,env=runtime_environment(arena,args.gpu),stdout=log,stderr=subprocess.STDOUT)
    save_json(output/'process.json',{'returncode':result.returncode})
    return result.returncode


if __name__=='__main__':
    raise SystemExit(main())
