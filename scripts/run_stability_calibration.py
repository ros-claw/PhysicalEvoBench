"""Preregistered full-horizon metric calibration, not learning evidence."""

import argparse
import random
from pathlib import Path

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds
from physicalevobench.stability.audit import assert_pairs, audit_worker, read
from physicalevobench.stability.study import launch, parallel


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    a = p.parse_args()
    root, out = Path(__file__).resolve().parents[1], Path(a.output).absolute()
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit calibration before physics')
    ref = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    source, hashes = snapshot_source(root, ref)
    excluded = published_seeds(root)
    for prior in out.parent.glob('peb-stability-*/registration.json'):
        reg = read(prior)
        for lane in reg.get('lanes', []):
            for recipe in lane['rounds']:
                excluded.update((recipe['environment_seed'], recipe['learner_seed']))
                excluded.update(c['seed'] for c in recipe['validation'])
        excluded.update(c['seed'] for group in reg.get('heldout', []) for c in group)
        excluded.update(c['seed'] for c in reg.get('preflight', []))
    rng = random.Random(202610241701)
    conditions = []
    for i in range(12):
        seed = rng.randrange(2**31)
        while seed in excluded:
            seed = rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id': f'envelope-calibration-{i:02d}', 'split': 'diagnostic',
                           'seed': seed, 'object_mass_kg': .1})
    checkpoint = '/home/dell/models/physicalevobench/franka_lift/model_1999.pt'
    cfg = {'checkpoint_path': checkpoint, 'checkpoint_sha256': sha256(checkpoint),
           'action_limit': 1000., 'physical_budget': 12, 'source_commit': ref}
    out.mkdir(parents=True)
    save_json(out/'registration.json', {'source_commit': ref, 'source_sha256': hashes,
              'registered_at': now(), 'conditions': conditions, 'physical_budget': 24,
              'criteria': {'original_holding_minimum': 8, 'original_instant_minimum': 10,
                           'open_gripper_holding_maximum': 0}})
    plans = []
    for arm, gpu in [('original', 2), ('open_gripper', 3)]:
        child = out/arm
        child.mkdir()
        save_json(child/'config.json', {**cfg, 'arm': arm, 'open_gripper': arm == 'open_gripper',
                  'jobs': [{'episode_id': f"{c['condition_id']}-{arm}", 'condition': c} for c in conditions]})
        plans.append((root, source, child, 'physicalevobench.stability.collect', gpu))
    parallel(launch, plans, 2)
    data = {arm: audit_worker(out/arm) for arm in ('original', 'open_gripper')}
    assert_pairs([(r, out/'original') for r in data['original']],
                 [(r, out/'open_gripper') for r in data['open_gripper']])
    counts = {arm: {'holding': sum(r['success'] for r in rows),
                    'instant': sum(r['stability']['instant_success'] for r in rows)} for arm, rows in data.items()}
    passed = counts['original']['holding'] >= 8 and counts['original']['instant'] >= 10 and counts['open_gripper']['holding'] == 0
    save_json(out/'results.json', {'status': 'PASS' if passed else 'CALIBRATION_FAILED', 'counts': counts,
                                 'physical_episodes': 24, 'learning_updates': 0})
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
