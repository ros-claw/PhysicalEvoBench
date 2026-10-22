"""Bounded training-only exploration of nine temporal candidates and identity replays."""

import argparse
import random
import subprocess
import time
from pathlib import Path

import yaml

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds


TRIALS = [
    ('hold10', {'gripper_hold_steps': 10}),
    ('hold25', {'gripper_hold_steps': 25}),
    ('hold50', {'gripper_hold_steps': 50}),
    ('hold100', {'gripper_hold_steps': 100}),
    ('hold250', {'gripper_hold_steps': 250}),
    ('smooth50', {'arm_smoothing_alpha': .5}),
    ('smooth20', {'arm_smoothing_alpha': .2}),
    ('hold50smooth50', {'gripper_hold_steps': 50, 'arm_smoothing_alpha': .5}),
    ('hold50smooth20', {'gripper_hold_steps': 50, 'arm_smoothing_alpha': .2}),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--gpus', type=int, nargs='+', default=[0, 1, 2])
    parser.add_argument('--guarded', action='store_true')
    args = parser.parse_args()
    trials = [
        ('guard2', {'finger_guard_enabled':True,'finger_margin_m':.002}),
        ('hold10guard2', {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.002}),
        ('hold10guard6', {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.006}),
        ('hold10guard10look2', {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.01,'finger_lookahead_steps':2}),
        ('guard6look2', {'finger_guard_enabled':True,'finger_margin_m':.006,'finger_lookahead_steps':2}),
        ('hold10guard3look0', {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.003,'finger_lookahead_steps':0}),
    ] if args.guarded else TRIALS
    if len(args.gpus)*3 != len(trials):
        raise ValueError('Use two GPUs for guarded exploration, three for temporal exploration')
    generator_seed = 202610221301 if args.guarded else 202610221101
    prefix = 'guarded' if args.guarded else 'temporal'
    root = Path(__file__).resolve().parents[1]
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit exploration code and plan before physics')
    output = Path(args.output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    config = yaml.safe_load((root / 'configs/confirmation.yaml').read_text())
    arena = (root / config['arena_path']).resolve()
    rng = random.Random(generator_seed)
    conditions = [{'condition_id': f'{prefix}-explore-train-{i:03d}', 'split': 'train',
                   'seed': rng.randrange(2**31), 'object_mass_kg': .8 + 2.4 * i / 7}
                  for i in range(8)]
    if {c['seed'] for c in conditions} & published_seeds(root):
        raise ValueError('Exploration seeds overlap previously published conditions')
    save_json(output / 'registration.json', {'registered_at': now(),
              'source_commit': command(['git', 'rev-parse', 'HEAD'], cwd=root),
              'plan_sha256': sha256(root / ('docs/experiments/GUARDED_EXPLORATION_PLAN.md' if args.guarded else 'docs/experiments/TEMPORAL_EXPLORATION_PLAN.md')),
              'conditions': conditions, 'trials': trials, 'physical_budget': len(args.gpus)*32,
              'heldout_test_budget': 0})
    jobs = []
    for group, gpu in enumerate(args.gpus):
        d = output / f'group-{group}'
        d.mkdir()
        trial_map = {'original': {}}
        trial_map.update(dict(trials[group * 3:group * 3 + 3]))
        cfg = dict(config, arena_path=str(arena), conditions=conditions, trials=trial_map,
                   physical_budget=32, order_seed=generator_seed + group,
                   skill_family='guarded-1' if args.guarded else 'temporal-1')
        save_json(d / 'config.json', cfg)
        launch = [str(arena_python_path(cfg, arena)), '-m',
                  'physicalevobench.evaluation.temporal_exploration', '--run-dir', str(d)]
        save_json(d / 'launch.json', {'command': launch, 'physical_gpu': gpu})
        log = (d / 'console.log').open('w')
        p = subprocess.Popen(launch, env=runtime_environment(arena, gpu),
                             stdout=log, stderr=subprocess.STDOUT)
        jobs.append((d, p, log))
    while any(p.poll() is None for _, p, _ in jobs):
        time.sleep(5)
    codes = {}
    for d, p, log in jobs:
        log.close()
        codes[d.name] = p.wait()
    save_json(output / 'processes.json', codes)
    return 0 if all(code == 0 for code in codes.values()) else 2


if __name__ == '__main__':
    raise SystemExit(main())
