"""Independent full-study verification; requires raw files, not a simulator."""

import argparse
import tempfile
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import assert_pairs, audit_worker, read
from physicalevobench.stability.metrics import promote
from physicalevobench.stability.study import summarize


def verify(out):
    out = Path(out)
    reg = read(out/'registration.json')
    expected_lanes = [(s, a) for s in range(3) for a in ('continual', 'restart')]
    if [(lane['seed'], lane['algorithm']) for lane in reg['lanes']] != expected_lanes:
        raise ValueError('Registered learning replication design changed')
    if len(reg['heldout']) != 3 or any(len(g) != 128 for g in reg['heldout']) or len(reg['preflight']) != 2:
        raise ValueError('Registered heldout/diagnostic sizes changed')
    if any(len(lane['rounds']) != 3 or any(len(r['validation']) != 64 for r in lane['rounds']) for lane in reg['lanes']):
        raise ValueError('Registered round/validation design changed')
    complete = read(out/'status.json')
    if complete['status'] != 'COMPLETED':
        raise ValueError('Study is incomplete; no positive scientific conclusion allowed')
    seen = set()
    for lane in reg['lanes']:
        for recipe in lane['rounds']:
            seeds = [recipe['learner_seed'], recipe['environment_seed']] + [c['seed'] for c in recipe['validation']]
            if seen.intersection(seeds) or len(seeds) != len(set(seeds)):
                raise ValueError('Training/validation seeds overlap')
            seen.update(seeds)
    for group in [*reg['heldout'], reg['preflight']]:
        seeds = [c['seed'] for c in group]
        if seen.intersection(seeds) or len(seeds) != len(set(seeds)):
            raise ValueError('Heldout/diagnostic seeds overlap')
        seen.update(seeds)
    workers = {}
    for cfg_path in sorted(out.rglob('config.json')):
        cfg = read(cfg_path)
        if 'jobs' in cfg:
            workers[cfg_path.parent] = audit_worker(cfg_path.parent)

    def evaluation(parent, conditions, arms):
        result = {arm: [] for arm in arms}
        pair_records = {arm: [] for arm in arms}
        for arm in arms:
            for child in sorted(parent.glob(f'block-*-{arm}')):
                if child not in workers:
                    raise ValueError('Missing registered worker')
                result[arm].extend(workers[child])
                pair_records[arm].extend((row, child) for row in workers[child])
                cfg, launch = read(child/'config.json'), read(child/'launch.json')
                if launch['runtime_source'] != reg['runtime_source']:
                    raise ValueError('Mutable or incorrect source launch')
                frozen = read(parent/'frozen_arms.json')[arm]
                if frozen['sha256'] != cfg['checkpoint_sha256']:
                    raise ValueError('Checkpoint differs from evaluation freeze')
            expected = [c['condition_id'] for c in conditions]
            if [r['condition_id'] for r in result[arm]] != expected:
                raise ValueError('Registered conditions missing/reordered')
        first = next(iter(pair_records.values()))
        for data in pair_records.values():
            assert_pairs(first, data)
        return result

    evaluation(out/'preflight', reg['preflight'], ['frozen'])
    trajectories = read(out/'all_trajectories_frozen.json')['trajectories']
    train_transitions = train_completed = train_unfinished = 0
    for lane, trajectory in zip(reg['lanes'], trajectories, strict=True):
        previous = reg['checkpoint_path']
        rate = .0001
        retained = reg['checkpoint_path']
        for i, recipe in enumerate(lane['rounds']):
            prefix = out/f"s{lane['seed']}-{lane['algorithm']}"/f'round-{i+1}'
            cfg = read(prefix/'train/config.json')
            if (cfg['num_envs'], cfg['iterations'], cfg['transition_budget']) != (128, 200, 614400):
                raise ValueError('Registered per-job training budget changed')
            expected_input = previous if lane['algorithm'] == 'continual' else reg['checkpoint_path']
            if cfg['checkpoint_path'] != expected_input or cfg['learning_rate'] != rate or cfg['learner_seed'] != recipe['learner_seed'] or cfg['environment_seed'] != recipe['environment_seed']:
                raise ValueError('Autonomous training lineage/rate/seeds mismatch')
            if cfg['source_commit'] != reg['source_commit'] or cfg['runtime_source_snapshot'] != reg['runtime_source']:
                raise ValueError('Training source mismatch')
            archive, audit = read(prefix/'train/training_archive.json'), read(prefix/'train/audit.json')
            if audit['status'] != 'PASS' or audit['transitions'] != 614400 or archive['transitions'] != 614400:
                raise ValueError('Training audit/budget mismatch')
            for chunk in archive['chunks']:
                if sha256(prefix/'train'/chunk['path']) != chunk['sha256']:
                    raise ValueError('Transition archive changed after audit')
            train_transitions += audit['transitions']
            train_completed += audit['completed_training_episodes']
            train_unfinished += audit['unfinished_rollout_steps']
            previous = cfg['candidate_path']
            rate = read(prefix/'model/next_recipe.json')['learning_rate']
            data = evaluation(prefix/'validation', recipe['validation'], ['incumbent', 'candidate'])
            candidate_frozen_at = read(prefix/'train/freeze.json')['frozen_at']
            if any(read(p)['started_at'] <= candidate_frozen_at for p in (prefix/'validation').glob('block-*/launch.json')):
                raise ValueError('Validation launched before candidate freeze')
            decision = read(prefix/'decision.json')
            reconstructed = promote(data['incumbent'], data['candidate'])
            for key in reconstructed:
                # JSON represents tuples as lists.
                if key in ('incumbent', 'candidate'):
                    reconstructed[key] = list(reconstructed[key])
                if decision[key] != reconstructed[key]:
                    raise ValueError('Promotion decision changed')
            if decision != trajectory['decisions'][i]:
                raise ValueError('Frozen decisions changed')
            if decision['promote']:
                retained = previous
            if trajectory['snapshots'][i] != retained:
                raise ValueError('Retained trajectory differs from private gate')
    if train_transitions != reg['training_budget']:
        raise ValueError('Total training budget mismatch')
    frozen_at = read(out/'all_trajectories_frozen.json')['frozen_at']
    heldout = []
    for seed in range(3):
        parent = out/f'heldout-s{seed}'
        for launch in parent.glob('block-*/launch.json'):
            if read(launch)['started_at'] <= frozen_at:
                raise ValueError('Heldout began before all learning stopped')
        heldout.append(evaluation(parent, reg['heldout'][seed],
                                  ['frozen', 'identity', 'round1', 'round2', 'round3', 'restart']))
    original_results = read(out/'results.json')
    # Recompute elsewhere so a failed comparison never replaces the submitted result.
    with tempfile.TemporaryDirectory(prefix='peb-stability-audit-') as scratch:
        reconstructed = summarize(Path(scratch), heldout, trajectories)
    if reconstructed != original_results:
        raise ValueError('Final scientific decision/statistics mismatch')
    episodes = sum(map(len, workers.values()))
    if episodes != 4610:
        raise ValueError('Total completed evaluation episodes mismatch')
    result = {'status': 'PASS', 'evaluation_episodes': episodes, 'workers': len(workers),
              'training_transitions': train_transitions, 'completed_training_episodes': train_completed,
              'unfinished_training_steps': train_unfinished, 'scientific_status': reconstructed['status'],
              'scope': 'raw evaluation recomputation, training archive hashes and prior tensor audits, seed/lineage/freeze/gate checks'}
    save_json(out/'delivery_audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True)
    print(verify(parser.parse_args().run_dir))
