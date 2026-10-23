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
    p.add_argument('--split',choices=['validation','heldout_test','diagnostic'],default='diagnostic')
    p.add_argument('--retention-decision')
    p.add_argument('--reuse-conditions')
    p.add_argument('--fresh-process', action='store_true')
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
                           'split': 'development' if a.mode == 'expert-pilot' else a.split,
                           'seed':seed, 'object_mass_kg': .1 if a.mode == 'measurement' else rng.uniform(.8, 3.2)})
    if a.reuse_conditions:
        conditions = list({j['condition']['condition_id']: j['condition'] for j in
                           json.loads(Path(a.reuse_conditions).read_text())['jobs']}.values())
    policies = {'measurement':['open_gripper', 'original', 'original'],
                'expert-pilot':['original', 'expert'], 'expert-test':['original', 'expert'],
                'replay':['original', 'original', 'original'], 'weights':['original', 'candidate']}[a.mode]
    if a.fresh_process:
        if a.mode != 'replay' or not a.reuse_conditions:
            raise ValueError('Fresh process comparison requires registered replay conditions')
        policies = ['original']
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
               fresh_process=a.fresh_process, registration_seed=a.registration_seed, registered_at=now(),
               source_commit=command(['git','rev-parse','HEAD'], cwd=root)['stdout'],
               policy_source_sha256=sha256(root/'physicalevobench/calibration/policies.py'),
               source_sha256={str(f.relative_to(root)):sha256(f) for f in (root/'physicalevobench').rglob('*.py')},
               criteria={'measurement':'original successes minus open-gripper successes >= 50 percentage points',
                         'expert-test':'paired superiority and sampled safety separately; no claim from pilot',
                         'replay':'describe discordance and initial-state/action differences; no pure GPU attribution',
                         'weights':'candidate frozen before paired evaluation; changed weights alone is not improvement'},
               additional_checkpoints={'candidate':str(Path(a.candidate).absolute())} if a.candidate else {})
    if a.retention_decision:
        decision_path = Path(a.retention_decision).absolute()
        decision = json.loads(decision_path.read_text())
        if a.mode != 'weights' or a.split != 'heldout_test':
            raise ValueError('Retention decisions apply only to heldout weight evaluations')
        retained = Path(decision['retained_checkpoint'])
        if sha256(retained) != decision['retained_checkpoint_sha256']:
            raise ValueError('Retained checkpoint changed after freeze')
        cfg['retention_decision_sha256'] = sha256(decision_path)
        cfg['additional_checkpoints'] = {'candidate':str(retained)}
        cfg['retention_decision'] = decision
    if a.mode == 'weights' and not a.candidate and not a.retention_decision:
        raise ValueError('Need frozen candidate checkpoint')
    cfg['additional_checkpoint_sha256'] = {k:sha256(v) for k,v in cfg['additional_checkpoints'].items()}
    save_json(out/'config.json', cfg)
    argv = [str(arena_python_path(cfg, arena)), '-m', 'physicalevobench.calibration.collect', '--run-dir', str(out)]
    save_json(out/'launch.json', {'argv':argv, 'gpu':a.gpu})
    if a.fresh_process:
        codes = []
        ledger = []
        for i, job in enumerate(jobs):
            ledger.append({'episode_id':job['episode_id'], 'reserved_at':now(), 'used':i+1})
            save_json(out/'budget_ledger.json', ledger)
            child = out/f'fresh-{i:03d}'
            child.mkdir()
            save_json(child/'config.json', {**cfg, 'jobs':[job], 'physical_budget':1})
            child_argv = [*argv[:-1], str(child)]
            with (child/'console.log').open('w') as log:
                result = subprocess.run(child_argv, cwd=arena, env=runtime_environment(arena,a.gpu),
                                        stdout=log, stderr=subprocess.STDOUT, timeout=600)
            save_json(child/'process.json', {'returncode':result.returncode, 'finished_at':now()})
            codes.append(result.returncode)
            if result.returncode:
                break
        code = int(any(codes))
        save_json(out/'status.json', {'status':'COMPLETED' if not code else 'INFRA_FAILURE',
                                    'physical_episodes':sum((out/f'fresh-{i:03d}'/'episodes.jsonl').exists() for i in range(len(codes)))})
    else:
        with (out/'console.log').open('w') as log:
            result = subprocess.run(argv, cwd=arena, env=runtime_environment(arena, a.gpu),
                                    stdout=log, stderr=subprocess.STDOUT, timeout=3600)
        code = result.returncode
    save_json(out/'process.json', {'returncode':code, 'finished_at':now()})
    return code


if __name__ == '__main__':
    raise SystemExit(main())
