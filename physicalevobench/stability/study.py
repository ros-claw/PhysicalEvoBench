"""Preregister and execute a bounded multiseed, multiround physics experiment."""

import argparse
import concurrent.futures
import random
import subprocess
from pathlib import Path

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds
from physicalevobench.stability.audit import assert_pairs, audit_worker, read
from physicalevobench.stability.metrics import paired_interval, promote


def launch(root, source, directory, module, gpu):
    arena = root/'external/IsaacLab-Arena'
    argv = [str(arena_python_path({}, arena)), '-m', module, '--run-dir', str(directory)]
    env = runtime_environment(arena, gpu)
    env['PYTHONPATH'] = str(source)
    save_json(directory/'launch.json', {'argv': argv, 'gpu': gpu, 'started_at': now(),
                                      'runtime_source': str(source)})
    with (directory/'console.log').open('w') as log:
        result = subprocess.run(argv, cwd=arena, env=env, stdout=log, stderr=subprocess.STDOUT,
                                timeout=7200)
    save_json(directory/'process.json', {'returncode': result.returncode, 'finished_at': now()})
    if result.returncode:
        raise RuntimeError(f'Native process failed: {directory}')


def parallel(function, plans, workers):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        # Consume every result: failures never become silently missing arms.
        futures = [pool.submit(function, *plan) for plan in plans]
        results, errors = [], []
        for future in futures:
            try:
                results.append(future.result())
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))
        return results


def register(root, out):
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit protocol and source before registration')
    ref = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    source, hashes = snapshot_source(root, ref)
    excluded = published_seeds(root)
    prior_registrations = []
    for path in sorted(out.parent.glob('peb-stability-*/registration.json')):
        previous = read(path)
        prior_registrations.append({'path': str(path), 'sha256': sha256(path)})
        for lane in previous['lanes']:
            for recipe in lane['rounds']:
                excluded.update((recipe['learner_seed'], recipe['environment_seed']))
                excluded.update(c['seed'] for c in recipe['validation'])
        excluded.update(c['seed'] for group in previous['heldout'] for c in group)
        excluded.update(c['seed'] for c in previous['preflight'])
    for path in (root/'runs').rglob('config.json'):
        cfg = read(path)
        excluded.update(j['condition']['seed'] for j in cfg.get('jobs', []))
        if 'environment_seed' in cfg:
            excluded.add(cfg['environment_seed'])
    rng = random.Random(2026102401)

    def fresh():
        value = rng.randrange(2**31)
        while value in excluded:
            value = rng.randrange(2**31)
        excluded.add(value)
        return value

    def conditions(name, count):
        return [{'condition_id': f'{name}-{i:03d}', 'seed': fresh(),
                 'object_mass_kg': rng.uniform(.8, 3.2), 'split': name.split('-')[0]}
                for i in range(count)]

    lanes = []
    for seed in range(3):
        for algorithm in ('continual', 'restart'):
            lanes.append({'seed': seed, 'algorithm': algorithm, 'rounds': [
                {'round': r, 'learner_seed': fresh(), 'environment_seed': fresh(),
                 'validation': conditions(f'validation-s{seed}-{algorithm}-r{r}', 64)}
                for r in range(1, 4)]})
    registration = {'schema': 'stability-1', 'registered_at': now(), 'source_commit': ref,
                    'runtime_source': str(source), 'source_sha256': hashes, 'lanes': lanes,
                    'heldout': [conditions(f'heldout-s{s}', 128) for s in range(3)],
                    'preflight': conditions('diagnostic-preflight', 2),
                    'training_budget': 11059200, 'validation_episode_budget': 2304,
                    'heldout_episode_budget': 2304, 'preflight_episode_budget': 2,
                    'checkpoint_path': '/home/dell/models/physicalevobench/franka_lift/model_1999.pt',
                    'checkpoint_sha256': 'babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa',
                    'prior_registrations': prior_registrations,
                    'protocol': 'docs/experiments/STABILITY_PROTOCOL_20261024.md'}
    if sha256(registration['checkpoint_path']) != registration['checkpoint_sha256']:
        raise ValueError('Base checkpoint changed')
    out.mkdir(parents=True, exist_ok=False)
    save_json(out/'registration.json', registration)
    return registration


def evaluation(root, source, parent, arms, conditions):
    plans, locations = [], {arm: [] for arm in arms}
    # Two or four blocks rotate each policy through separate native GPU workers.
    block_size = 32
    for block, offset in enumerate(range(0, len(conditions), block_size)):
        for arm_index, (arm, checkpoint) in enumerate(arms.items()):
            child = parent/f'block-{block}-{arm}'
            child.mkdir(parents=True)
            cfg = {'arm': arm, 'checkpoint_path': str(checkpoint), 'checkpoint_sha256': sha256(checkpoint),
                   'physical_budget': len(conditions[offset:offset+block_size]),
                   'jobs': [{'episode_id': f"{c['condition_id']}-{arm}", 'condition': c}
                            for c in conditions[offset:offset+block_size]]}
            save_json(child/'config.json', cfg)
            plans.append((root, source, child, 'physicalevobench.stability.collect', (block+arm_index)%4))
            locations[arm].append(child)
    save_json(parent/'frozen_arms.json', {a: {'path': str(p), 'sha256': sha256(p)} for a, p in arms.items()})
    parallel(launch, plans, 4)
    results = {arm: [(row, path) for path in paths for row in audit_worker(path)]
               for arm, paths in locations.items()}
    first = next(iter(results.values()))
    for arm in results.values():
        assert_pairs(first, arm)
    return {arm: [row for row, _ in data] for arm, data in results.items()}


def training(root, source, path, cfg, gpu):
    path.mkdir(parents=True)
    Path(cfg['candidate_path']).parent.mkdir(parents=True)
    save_json(path/'config.json', cfg)
    launch(root, source, path, 'physicalevobench.calibration.train', gpu)
    arena = root/'external/IsaacLab-Arena'
    env = runtime_environment(arena, gpu)
    env['PYTHONPATH'] = str(source)
    with (path/'audit_console.log').open('w') as log:
        result = subprocess.run([str(arena_python_path({}, arena)), '-m',
                                 'physicalevobench.calibration.training_audit', '--run-dir', str(path)],
                                cwd=arena, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode:
        raise RuntimeError(f'Training re-audit failed: {path}')
    return read(path/'freeze.json')


def summarize(out, heldout, trajectories):
    comparisons = {}
    for r in range(1, 4):
        for base in ('frozen', 'identity'):
            comparisons[f'round{r}_vs_{base}'] = paired_interval([
                [int(a['success'])-int(b['success']) for a, b in zip(seed[f'round{r}'], seed[base], strict=True)]
                for seed in heldout], alpha=.05/6)
    for r in (2, 3):
        comparisons[f'round{r}_vs_previous'] = paired_interval([
            [int(a['success'])-int(b['success']) for a, b in zip(seed[f'round{r}'], seed[f'round{r-1}'], strict=True)]
            for seed in heldout], alpha=.05/2)
    comparisons['final_vs_restart'] = paired_interval([
        [int(a['success'])-int(b['success']) for a, b in zip(seed['round3'], seed['restart'], strict=True)]
        for seed in heldout])
    safety = []
    for seed in heldout:
        old, new = seed['frozen'], seed['round3']
        check = promote(old, new)
        any_difference = sum(r['safety']['any_violation'] for r in new)/len(new) - sum(r['safety']['any_violation'] for r in old)/len(old)
        safety.append({'per_joint_depth_guard': check['per_joint_depth_guard'],
                       'sample_count_guard': check['candidate'][2] <= check['incumbent'][2],
                       'normalized_guard': check['candidate'][2]/check['candidate'][3] <= check['incumbent'][2]/check['incumbent'][3],
                       'any_violation_rate_difference': any_difference,
                       'pass': check['per_joint_depth_guard'] and check['candidate'][2] <= check['incumbent'][2]
                       and check['candidate'][2]/check['candidate'][3] <= check['incumbent'][2]/check['incumbent'][3]
                       and any_difference <= .05})
    gates = {
        'all_rounds_beat_both_frozen_controls': all(v['interval'][0] > 0 for k, v in comparisons.items() if '_vs_frozen' in k or '_vs_identity' in k),
        'each_seed_final_gain_positive': all(x > 0 for key in ('round3_vs_frozen', 'round3_vs_identity') for x in comparisons[key]['per_seed_difference']),
        'consecutive_nonregression': all(comparisons[f'round{r}_vs_previous']['interval'][0] >= -.05 and comparisons[f'round{r}_vs_previous']['difference'] >= 0 for r in (2, 3)),
        'two_actual_promotions_each_seed': all(sum(t['decisions'][r]['promote'] for r in range(3)) >= 2 for t in trajectories if t['algorithm'] == 'continual'),
        'sampled_safety_guards': all(s['pass'] for s in safety),
    }
    result = {'status': 'STABLE_BOUNDED_ADAPTATION_SUPPORTED' if all(gates.values()) else 'STABLE_SELF_EVOLUTION_NOT_ESTABLISHED',
              'gates': gates, 'comparisons': comparisons, 'safety_per_seed': safety,
              'equal_budget_advantage_supported': comparisons['final_vs_restart']['interval'][0] > 0,
              'counts': [{arm: {'stable': sum(r['success'] for r in data), 'instant': sum(r['stability']['instant_success'] for r in data), 'episodes': len(data)} for arm, data in seed.items()} for seed in heldout],
              'scope': '3 learned trajectories, 3 rounds, this simulator/task/mass range/5-second horizon; no unlimited or general self-evolution claim'}
    save_json(out/'results.json', result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--root', default=str(Path.cwd()))
    args = p.parse_args()
    root, out = Path(args.root).absolute(), Path(args.output).absolute()
    reg = register(root, out)
    source, original = Path(reg['runtime_source']), Path(reg['checkpoint_path'])
    try:
        evaluation(root, source, out/'preflight', {'frozen': original}, reg['preflight'])
        trajectories = [{'seed': lane['seed'], 'algorithm': lane['algorithm'], 'input': original,
                         'retained': original, 'rate': .0001, 'snapshots': [], 'decisions': []}
                        for lane in reg['lanes']]
        for round_index in range(3):
            plans = []
            for i, (lane, t) in enumerate(zip(reg['lanes'], trajectories, strict=True)):
                prefix = out/f"s{lane['seed']}-{lane['algorithm']}"/f'round-{round_index+1}'
                t['prefix'] = prefix
                candidate = prefix/'model/model_final.pt'
                input_model = t['input'] if lane['algorithm'] == 'continual' else original
                recipe = lane['rounds'][round_index]
                cfg = {'stability_study': True, 'checkpoint_path': str(input_model),
                       'checkpoint_sha256': sha256(input_model), 'candidate_path': str(candidate),
                       'num_envs': 128, 'iterations': 200, 'transition_budget': 614400,
                       'learner_seed': recipe['learner_seed'], 'environment_seed': recipe['environment_seed'],
                       'learning_rate': t['rate'], 'source_commit': reg['source_commit'],
                       'runtime_source_snapshot': str(source)}
                plans.append((root, source, prefix/'train', cfg, i%3))
            parallel(training, plans, 3)
            # All training in this round finishes before any private validation is read.
            for lane, t in zip(reg['lanes'], trajectories, strict=True):
                prefix = t['prefix']
                candidate = prefix/'model/model_final.pt'
                t['input'] = candidate
                t['rate'] = read(candidate.parent/'next_recipe.json')['learning_rate']
                data = evaluation(root, source, prefix/'validation',
                                  {'incumbent': t['retained'], 'candidate': candidate},
                                  lane['rounds'][round_index]['validation'])
                decision = promote(data['incumbent'], data['candidate'])
                decision.update(candidate_sha256=sha256(candidate), incumbent_sha256=sha256(t['retained']), decided_at=now())
                if decision['promote']:
                    t['retained'] = candidate
                t['decisions'].append(decision)
                t['snapshots'].append(t['retained'])
                save_json(prefix/'decision.json', decision)
            save_json(out/f'round-{round_index+1}-completed.json', {'finished_at': now()})
        frozen = [{**t, 'input': str(t['input']), 'prefix': str(t['prefix']),
                   'retained': str(t['retained']), 'snapshots': [str(p) for p in t['snapshots']]}
                  for t in trajectories]
        save_json(out/'all_trajectories_frozen.json', {'frozen_at': now(), 'trajectories': frozen})
        heldout = []
        for seed in range(3):
            main_lane, control = trajectories[seed*2:seed*2+2]
            arms = {'frozen': original, 'identity': original,
                    **{f'round{i+1}': p for i, p in enumerate(main_lane['snapshots'])},
                    'restart': control['retained']}
            heldout.append(evaluation(root, source, out/f'heldout-s{seed}', arms, reg['heldout'][seed]))
        summarize(out, heldout, trajectories)
        save_json(out/'status.json', {'status': 'COMPLETED', 'finished_at': now(),
                                     'evaluation_episodes': 4610, 'training_transitions': 11059200})
    except Exception as error:
        save_json(out/'status.json', {'status': 'INFRA_FAILURE', 'error': str(error), 'at': now()})
        raise


if __name__ == '__main__':
    main()
