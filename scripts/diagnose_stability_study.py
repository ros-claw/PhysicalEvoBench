"""Pre-heldout-defined diagnostics; never changes registered scientific decisions."""

import argparse
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read, rows
from physicalevobench.stability.metrics import paired_interval, promote


def safety_comparison(old, new):
    gate = promote(old, new)
    a, b = gate['incumbent'], gate['candidate']
    episode_delta = sum(r['safety']['any_violation'] for r in new)/len(new) - sum(r['safety']['any_violation'] for r in old)/len(old)
    guards = {'raw_count': b[2] <= a[2], 'normalized_count': b[2]/b[3] <= a[2]/a[3],
              'per_joint_depth': gate['per_joint_depth_guard'], 'any_episode_rate': episode_delta <= .05}
    return {'guards': guards, 'pass': all(guards.values()), 'old_count_exposure': [a[2], a[3]],
            'new_count_exposure': [b[2], b[3]], 'any_violation_rate_difference': episode_delta}


def diagnose(out):
    out = Path(out)
    if read(out/'status.json')['status'] != 'COMPLETED':
        raise ValueError('Diagnostics require the completed fixed study')
    reg = read(out/'registration.json')
    if sha256(out/'registration.json') != '2fc99ba2e4f4a0d9d8a37c58ced7cc21c27df5877d9b8fb7455cf7e15b7ac260':
        raise ValueError('This supplement was preregistered for a different study')
    arms = ['frozen', 'identity', 'round1', 'round2', 'round3', 'restart']
    blocks, identity_safety = [], []
    effects = {base: [] for base in ('frozen', 'identity')}
    for seed in range(3):
        full = {arm: [] for arm in arms}
        per_seed = {base: [] for base in effects}
        for block in range(4):
            data = {arm: rows(out/f'heldout-s{seed}'/f'block-{block}-{arm}'/'episodes.jsonl') for arm in arms}
            if any(len(r) != 32 for r in data.values()):
                raise ValueError('Incomplete heldout process block')
            expected_ids = [c['condition_id'] for c in reg['heldout'][seed][32*block:32*(block+1)]]
            if any([r['condition_id'] for r in group] != expected_ids for group in data.values()):
                raise ValueError('Block condition order mismatch')
            for arm in arms:
                full[arm].extend(data[arm])
            counts = {arm: sum(r['success'] for r in data[arm]) for arm in arms}
            blocks.append({'seed': seed, 'block': block, 'conditions': 32, 'successes': counts})
            for base in effects:
                per_seed[base].append((counts['round3']-counts[base])/32)
        for base in effects:
            effects[base].append(per_seed[base])
        if any(r['base_checkpoint_sha256'] != reg['checkpoint_sha256'] for arm in ('frozen', 'identity') for r in full[arm]):
            raise ValueError('Identity diagnostic used different weights')
        identity_safety.append({'seed': seed, **safety_comparison(full['frozen'], full['identity'])})
    intervals = {}
    for base, groups in effects.items():
        value = paired_interval(groups, alpha=.05/2)
        value.update(clusters=value.pop('conditions'), conditions=384,
                     scope='paired process-block resampling within three fixed learned trajectories; not a population-of-learners interval')
        intervals['final_vs_'+base] = value
    result = {'process_blocks': blocks, 'block_bootstrap': intervals,
              'identity_safety': identity_safety, 'changes_primary_decision': False,
              'main_registration_sha256': sha256(out/'registration.json'),
              'analysis_source_sha256': sha256(Path(__file__)),
              'block_intervals_both_positive': all(d['interval'][0] > 0 for d in intervals.values())}
    save_json(out/'supplemental_diagnostics.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    result = diagnose(p.parse_args().run_dir)
    print('Block diagnostics complete; corroboration:', result['block_intervals_both_positive'])
