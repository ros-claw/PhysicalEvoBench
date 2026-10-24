"""Separately registered raw-final-policy diagnosis; cannot rescue the main verdict."""

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.stability.audit import assert_pairs, assert_registered_assignment, audit_worker, read
from physicalevobench.stability.metrics import paired_interval, promote
from physicalevobench.stability.study import evaluation


ARMS = ('frozen', 'raw_continual', 'raw_restart')


def summarize(data):
    comparisons = {}
    for new, old in [('raw_continual', 'frozen'), ('raw_restart', 'frozen'), ('raw_continual', 'raw_restart')]:
        comparisons[new+'_vs_'+old] = paired_interval([
            [int(a['success'])-int(b['success']) for a, b in zip(seed[new], seed[old], strict=True)]
            for seed in data], alpha=.05/3)
    safety = []
    for seed in data:
        group = {}
        for arm in ARMS[1:]:
            item = promote(seed['frozen'], seed[arm])
            item['would_meet_point_gate_on_diagnostic_set'] = item.pop('promote')
            group[arm] = item
        safety.append(group)
    return {'role': 'SEPARATE_DIAGNOSTIC_NOT_STABILITY_CONFIRMATION',
            'comparisons': comparisons, 'descriptive_gate_checks': safety,
            'counts': [{arm: sum(row['success'] for row in seed[arm]) for arm in ARMS} for seed in data],
            'episodes': 576, 'unique_conditions': 192, 'learning_updates': 0,
            'main_scientific_decision_unchanged': True,
            'scope': 'latest raw candidates only; no best-of-run selection, no promotion override, no stable-evolution claim'}


def audit_probe(out):
    out = Path(out)
    reg, all_data = read(out/'registration.json'), []
    if reg['schema'] != 'raw-policy-probe-1' or len(reg['conditions']) != 3:
        raise ValueError('Unexpected raw probe design')
    if read(out/'status.json')['status'] != 'COMPLETED' or any(len(group) != 64 for group in reg['conditions']):
        raise ValueError('Incomplete raw policy probe')
    if sha256(out/'main_registration.json') != reg['main_registration_sha256']:
        raise ValueError('Parent study registration changed')
    seeds = [c['seed'] for group in reg['conditions'] for c in group]
    if len(set(seeds)) != 192 or set(seeds) & registered_seed_values(read(out/'main_registration.json')):
        raise ValueError('Diagnostic seeds repeat or overlap the parent study')
    completed = 0
    for seed in range(3):
        pairs = {arm: [] for arm in ARMS}
        parent = out/f'trajectory-{seed}'
        frozen = read(parent/'frozen_arms.json')
        for arm in ARMS:
            children = sorted(parent.glob('block-*-'+arm))
            if children != [parent/f'block-{b}-{arm}' for b in range(4)]:
                raise ValueError('Registered diagnostic process blocks changed')
            for block, child in enumerate(children):
                cfg = read(child/'config.json')
                assert_registered_assignment(cfg, reg['conditions'][seed][16*block:16*(block+1)],
                                             arm, reg['model_path_plan'][seed][arm], frozen[arm]['sha256'])
                if cfg['checkpoint_sha256'] != frozen[arm]['sha256'] or cfg['checkpoint_path'] != frozen[arm]['path'] or cfg.get('official_mode') is not True or cfg.get('action_limit') != 1000.:
                    raise ValueError('Raw probe model/interface mismatch')
                if read(child/'launch.json')['runtime_source'] != reg['runtime_source']:
                    raise ValueError('Raw probe source mismatch')
                if read(child/'launch.json')['started_at'] <= read(out/'all_models_frozen.json')['frozen_at']:
                    raise ValueError('Probe launched before all assignments froze')
                records = audit_worker(child)
                pairs[arm].extend((r, child) for r in records)
                completed += len(records)
            if [r['condition_id'] for r, _ in pairs[arm]] != [c['condition_id'] for c in reg['conditions'][seed]]:
                raise ValueError('Probe conditions differ from registration')
            if frozen[arm]['sha256'] != read(out/'all_models_frozen.json')['models'][seed][arm]['sha256']:
                raise ValueError('Raw model freeze mismatch')
            if frozen[arm]['path'] != reg['model_path_plan'][seed][arm]:
                raise ValueError('Diagnostic model was selected outside the preregistered path plan')
            if arm == 'frozen' and frozen[arm]['sha256'] != reg['checkpoint_sha256']:
                raise ValueError('Original probe checkpoint changed')
            if arm != 'frozen' and frozen[arm]['sha256'] != read(out/'main_training_freezes.json')[seed][arm]['candidate_sha256']:
                raise ValueError('Diagnostic model differs from the raw training freeze')
        for records in pairs.values():
            assert_pairs(pairs['frozen'], records)
        all_data.append({arm: [r for r, _ in records] for arm, records in pairs.items()})
    result = summarize(all_data)
    # JSON converts tuples to lists in promotion diagnostics.
    result = json.loads(json.dumps(result))
    if completed != 576 or result != read(out/'results.json'):
        raise ValueError('Raw policy diagnostic outcome or cost changed')
    return {'status': 'PASS', 'episodes': completed, 'scientific_role': result['role'],
            'main_decision_overridden': False}


def render_report(out, output):
    out = Path(out)
    result, verdict = read(out/'results.json'), read(out/'main_verdict.json')
    text = ['# Raw final-policy diagnosis after retention-gate failures', '',
            f"**Main confirmation outcome remains `{verdict['status']}`.**", '',
            'This separately registered diagnostic compares every trajectory\'s latest raw round-3 '
            'candidate to the original and latest raw restart candidate. It adds no training and '
            'overrides no promotion. It cannot rescue the failed main stability confirmation.', '',
            '[Protocol](RAW_POLICY_PROBE_PROTOCOL_20261024.md). '
            '[Main results](STABILITY_RESULTS_20261024.md). '
            '[Raw evidence manifest](../evidence/raw-policy-probe-20261024/manifest.json).', '',
            '| Trajectory | Original /64 | Raw continual /64 | Latest raw restart /64 |',
            '| --- | --- | --- | --- |']
    for seed, counts in enumerate(result['counts']):
        text.append('| '+str(seed)+' | '+' | '.join(str(counts[arm]) for arm in ARMS)+' |')
    text += ['', '| Comparison | Official-success difference (pp) | Adjusted conditional interval (pp) |',
             '| --- | --- | --- |']
    for name, value in result['comparisons'].items():
        lo, hi = value['interval']
        text.append(f"| {name} | {value['difference']*100:+.2f} | [{lo*100:+.2f}, {hi*100:+.2f}] |")
    text += ['', '10,000 paired condition-bootstrap draws within three fixed learned trajectories, '
             'Bonferroni alpha=0.05/3. These intervals do not establish population-level stability or '
             'a safety guarantee. The restart arm is the last candidate, not a best-of-three oracle.', '',
             '| Trajectory | Raw arm | Original / new violation samples | Original / new exposure | Per-joint depth margin passes |',
             '| --- | --- | --- | --- | --- |']
    for seed, checks in enumerate(result['descriptive_gate_checks']):
        for arm, gate in checks.items():
            a, b = gate['incumbent'], gate['candidate']
            text.append(f"| {seed} | {arm} | {a[2]} / {b[2]} | {a[3]} / {b[3]} | {gate['per_joint_depth_guard']} |")
    text += ['', 'A raw task-success gain accompanied by failed safety or retention criteria is an '
             'unaccepted candidate. It does not become a retroactive promotion. A weak raw gain '
             'would instead limit this particular learning recipe. Nominal/deep holding, contact '
             'safety, future learning seeds and indefinite self-improvement are not established.', '',
             'Cost: 576 actual evaluation episodes on 192 unique paired conditions, zero new '
             'optimizer iterations. All nine checkpoint assignments froze before the first launch; '
             'no extra GPU process ran during the primary confirmation. Per-policy native '
             'processes, raw physical readbacks/actions/outcomes, matched initial observations '
             'and sampled safety were independently audited. No checkpoint weights are distributed.', '']
    Path(output).write_text('\n'.join(text))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--main-run', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--evidence')
    p.add_argument('--verify-output')
    p.add_argument('--report', default='docs/experiments/RAW_POLICY_PROBE_RESULTS_20261024.md')
    args = p.parse_args()
    root, main_out, out = Path.cwd(), Path(args.main_run).absolute(), Path(args.output).absolute()
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit the separate diagnostic before registration')
    main_reg = read(main_out/'registration.json')
    ref = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    source, hashes = snapshot_source(root, ref)
    excluded = published_seeds(root) | registered_seed_values(main_reg)
    rng, conditions = random.Random(202610242301), []
    for trajectory in range(3):
        group = []
        for i in range(64):
            seed = rng.randrange(2**31)
            while seed in excluded:
                seed = rng.randrange(2**31)
            excluded.add(seed)
            group.append({'condition_id': f'raw-probe-s{trajectory}-{i:03d}', 'split': 'diagnostic_test',
                          'seed': seed, 'object_mass_kg': rng.uniform(.8, 3.2)})
        conditions.append(group)
    out.mkdir(parents=True, exist_ok=False)
    reg = {'schema': 'raw-policy-probe-1', 'source_commit': ref, 'source_sha256': hashes,
           'runtime_source': str(source), 'registered_at': now(), 'conditions': conditions,
           'main_registration_sha256': sha256(main_out/'registration.json'), 'physical_budget': 576,
           'checkpoint_path': main_reg['checkpoint_path'], 'checkpoint_sha256': main_reg['checkpoint_sha256'],
           'selection_rule': 'round 3 raw continual/restart for all three trajectories, regardless of validation',
           'model_path_plan': [{
               'frozen': main_reg['checkpoint_path'],
               'raw_continual': str(main_out/f's{s}-continual/round-3/model/model_final.pt'),
               'raw_restart': str(main_out/f's{s}-restart/round-3/model/model_final.pt')} for s in range(3)],
           'protocol': 'docs/experiments/RAW_POLICY_PROBE_PROTOCOL_20261024.md'}
    save_json(out/'registration.json', reg)
    shutil.copyfile(main_out/'registration.json', out/'main_registration.json')
    audited = False
    try:
        # No extra GPU worker is introduced while the registered primary study is running.
        while True:
            try:
                status = read(main_out/'status.json')
            except (FileNotFoundError, json.JSONDecodeError):
                status = None
            if status:
                if status['status'] != 'COMPLETED':
                    raise RuntimeError('Main experiment failed to complete; no raw probe launched')
                break
            time.sleep(10)
        save_json(out/'main_verdict.json', read(main_out/'results.json'))
        models, training_freezes = [], []
        for seed in range(3):
            arms = {arm: Path(path) for arm, path in reg['model_path_plan'][seed].items()}
            models.append({arm: {'path': str(path), 'sha256': sha256(path)} for arm, path in arms.items()})
            training_freezes.append({})
            for arm, algorithm in [('raw_continual', 'continual'), ('raw_restart', 'restart')]:
                training_freezes[-1][arm] = read(main_out/f's{seed}-{algorithm}/round-3/train/freeze.json')
                if models[-1][arm]['sha256'] != training_freezes[-1][arm]['candidate_sha256']:
                    raise ValueError('Latest raw checkpoint changed after training freeze')
            if models[-1]['frozen']['sha256'] != reg['checkpoint_sha256']:
                raise ValueError('Original checkpoint changed before the diagnostic')
        save_json(out/'all_models_frozen.json', {'frozen_at': now(), 'models': models})
        save_json(out/'main_training_freezes.json', training_freezes)
        data = []
        for seed in range(3):
            data.append(evaluation(root, source, out/f'trajectory-{seed}',
                                   {arm: Path(spec['path']) for arm, spec in models[seed].items()}, conditions[seed]))
        save_json(out/'results.json', summarize(data))
        save_json(out/'status.json', {'status': 'COMPLETED', 'episodes': 576, 'finished_at': now()})
        save_json(out/'audit.json', audit_probe(out))
        audited = True
        render_report(out, root/args.report)
        if args.evidence:
            argv = [sys.executable, 'scripts/package_stability_study.py', '--run-dir', str(out), '--output', args.evidence]
            with (out.parent/(out.name+'-package.log')).open('w') as log:
                code = subprocess.run(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=3600).returncode
            if code:
                raise RuntimeError('Raw probe packaging failed')
            if args.verify_output:
                with (out.parent/(out.name+'-public-verify.log')).open('w') as log:
                    code = subprocess.run([sys.executable, 'scripts/verify_stability_delivery.py', '--evidence', args.evidence,
                                           '--output', args.verify_output], cwd=root, stdout=log,
                                          stderr=subprocess.STDOUT, timeout=3600).returncode
                if code:
                    raise RuntimeError('Raw probe public verification failed')
    except Exception as error:
        target = out.parent/(out.name+'-delivery-failure.json') if audited else out/'status.json'
        save_json(target, {'status': 'DELIVERY_FAILURE' if audited else 'INFRA_FAILURE', 'error': str(error), 'at': now()})
        raise


if __name__ == '__main__':
    main()
