"""Prospectively register and supervise bounded real calibration jobs."""

import argparse
import json
import random
import subprocess
from pathlib import Path

import yaml

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--mode', choices=['measurement', 'expert-pilot', 'expert-test', 'replay', 'weights'], required=True)
    p.add_argument('--gpu', type=int, default=0)
    p.add_argument('--registration-seed', type=int, required=True)
    p.add_argument('--conditions', type=int, default=12)
    p.add_argument('--candidate')
    p.add_argument('--reuse-conditions')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit source before registration')
    cfg = yaml.safe_load((root/'configs/confirmation.yaml').read_text())
    rng = random.Random(a.registration_seed)
    excluded = published_seeds(root)
    for f in (root/'runs').glob('calibration-*/config.json'):
        excluded.update(j['condition']['seed'] for j in json.loads(f.read_text()).get('jobs', []))
    conditions = []
    for i in range(a.conditions):
        seed = rng.randrange(2**31)
        while seed in excluded:
            seed = rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id': f'{a.mode}-{a.registration_seed}-{i:03d}',
                           'split': 'development' if a.mode == 'expert-pilot' else 'diagnostic',
                           'seed':seed, 'object_mass_kg': .1 if a.mode == 'measurement' else rng.uniform(.8, 3.2)})
    if a.reuse_conditions:
        conditions = list({j['condition']['condition_id']: j['condition'] for j in
                           json.loads(Path(a.reuse_conditions).read_text())['jobs']}.values())
    policies = {'measurement':['open_gripper', 'original', 'original'],
                'expert-pilot':['original', 'expert'], 'expert-test':['original', 'expert'],
                'replay':['original', 'original', 'original'], 'weights':['original', 'candidate']}[a.mode]
    jobs = []
    for condition in conditions:
        order = list(enumerate(policies))
        rng.shuffle(order)
        for repeat, policy in order:
            jobs.append({'episode_id':f"{condition['condition_id']}-{repeat}-{policy}",
                         'policy':policy, 'condition':condition})
    out = Path(a.output).absolute()
    out.mkdir(parents=True, exist_ok=False)
    arena = (root/cfg['arena_path']).resolve()
    cfg.update(schema_version='calibration-1', mode=a.mode, jobs=jobs, physical_budget=len(jobs),
               registration_seed=a.registration_seed, registered_at=now(),
               source_commit=command(['git','rev-parse','HEAD'], cwd=root)['stdout'],
               policy_source_sha256=sha256(root/'physicalevobench/calibration/policies.py'),
               source_sha256={str(f.relative_to(root)):sha256(f) for f in (root/'physicalevobench').rglob('*.py')},
               criteria={'measurement':'original successes minus open-gripper successes >= 50 percentage points',
                         'expert-test':'paired superiority and sampled safety separately; no claim from pilot',
                         'replay':'describe discordance and initial-state/action differences; no pure GPU attribution',
                         'weights':'candidate frozen before paired evaluation; changed weights alone is not improvement'},
               additional_checkpoints={'candidate':str(Path(a.candidate).absolute())} if a.candidate else {})
    if a.mode == 'weights' and not a.candidate:
        raise ValueError('Need frozen candidate checkpoint')
    save_json(out/'config.json', cfg)
    argv = [str(arena_python_path(arena)), '-m', 'physicalevobench.calibration.collect', '--run-dir', str(out)]
    save_json(out/'launch.json', {'argv':argv, 'gpu':a.gpu})
    with (out/'console.log').open('w') as log:
        result = subprocess.run(argv, cwd=arena, env=runtime_environment(arena, a.gpu),
                                stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    save_json(out/'process.json', {'returncode':result.returncode, 'finished_at':now()})
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
