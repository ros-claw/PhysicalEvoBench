"""Targeted offline diagnosis, with no new episodes and no historical rejudgment."""

import argparse
import gzip
import json
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read
from physicalevobench.stability.metrics import train_recipe as legacy_recipe
from physicalevobench.v02.metrics import train_recipe


def records(path):
    with gzip.open(path, 'rt') as stream:
        return [json.loads(line) for line in stream]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--main-study', required=True)
    p.add_argument('--probe', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    study, probe, out = Path(a.main_study), Path(a.probe), Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    schedules = []
    for path in sorted(study.glob('s*-*/round-*/model/public_reward_means.json')):
        recipe = read(path.parent/'next_recipe.json')
        cfg = read(path.parent.parent/'train/config.json')
        old, new = legacy_recipe(read(path), cfg['learning_rate']), train_recipe(read(path), cfg['learning_rate'])
        if old != recipe:
            raise ValueError('Historical scheduler differs from the frozen recorded recipe')
        schedules.append({'job': str(path.parent.parent.relative_to(study)),
                          'reward_summary_sha256': sha256(path), 'legacy': old, 'v02_counterfactual': new,
                          'rate_would_change': old['learning_rate'] != new['learning_rate']})
    selected = []
    for arm in ('frozen', 'raw_continual', 'raw_restart'):
        rows = [(json.loads(line), path.parent) for path in sorted(probe.glob(f'trajectory-*/block-*-{arm}/episodes.jsonl'))
                for line in path.read_text().splitlines()]
        def depth(item):
            return max(j['maximum_depth'] for j in item[0]['safety']['per_joint'] if j['unit'] == 'm')
        categories = {'deepest_finger': rows,
                      'success_with_violation': [v for v in rows if v[0]['success'] and v[0]['safety']['any_violation']],
                      'failure_without_violation': [v for v in rows if not v[0]['success'] and not v[0]['safety']['any_violation']]}
        for category, candidates in categories.items():
            if not candidates:
                selected.append({'arm': arm, 'category': category, 'status': 'NO_ELIGIBLE_EPISODE'})
                continue
            row, directory = sorted(candidates, key=lambda v: (-depth(v), v[0]['condition_id'], str(v[1])))[0]
            initial = read(directory/row['initial_state_artifact'])
            trace = records(directory/row['trace_artifact'])
            first = None
            for frame in trace:
                violations = [{'joint': j['joint'], 'position': frame['joint_position'][0][k],
                               'limits': initial['joint_limits'][0][k]}
                              for k, j in enumerate(row['safety']['per_joint'])
                              if max(initial['joint_limits'][0][k][0]-frame['joint_position'][0][k],
                                     frame['joint_position'][0][k]-initial['joint_limits'][0][k][1], 0) > .001]
                if violations:
                    first = {'control_step': frame['step'], 'time_s': frame['step']*.02,
                             'violations': violations, 'raw_action': frame['raw_action'],
                             'applied_action': frame['applied_action'], 'joint_velocity': frame['joint_velocity']}
                    break
            save_json(out/(arm+'-'+category+'.json'), {'initial': initial, 'episode': row,
                                                      'first_violation': first})
            selected.append({'arm': arm, 'category': category, 'episode_id': row['episode_id'],
                             'condition': initial['condition'], 'worker': str(directory),
                             'checkpoint_path': read(directory/'config.json')['checkpoint_path'],
                             'checkpoint_sha256': row['base_checkpoint_sha256'],
                             'trace_sha256': sha256(directory/row['trace_artifact']),
                             'success': row['success'], 'maximum_finger_depth': depth((row, directory)),
                             'first_violation': first,
                             'missing': ['processed_joint_targets', 'contact_forces', 'terminal_pre_reset_state']})
    divergences = []
    for s in range(3):
        for block in range(4):
            base = study/f'heldout-s{s}'
            paths = [base/f'block-{block}-{arm}' for arm in ('frozen', 'identity')]
            rows = [[json.loads(line) for line in (path/'episodes.jsonl').read_text().splitlines()] for path in paths]
            for left, right in zip(*rows, strict=True):
                traces = [records(path/row['trace_artifact']) for path, row in zip(paths, (left, right), strict=True)]
                first = {}
                for k, (x, y) in enumerate(zip(*traces)):
                    for key in ('joint_position', 'object_position', 'raw_action'):
                        if key not in first and x[key] != y[key]:
                            first[key] = k
                divergences.append({'condition_id': left['condition_id'], 'first_exact_difference_control_step': first,
                                    'lengths': list(map(len, traces)),
                                    'successes': [left['success'], right['success']],
                                    'scope': 'exact recorded values; separate GPU/process blocks, not unique causal attribution'})
    result = {'schema': 'v02-focused-history-diagnosis', 'new_physics_episodes': 0,
              'sample_selection': 'per arm/category, greatest finger depth; ties by condition id and worker path',
              'scheduler_jobs': schedules, 'scheduler_changed_count': sum(v['rate_would_change'] for v in schedules),
              'representatives': selected, 'identity_first_divergences': divergences,
              'historical_decisions_changed': False}
    save_json(out/'history_diagnosis.json', result)
    print({'scheduler_jobs': len(schedules), 'counterfactual_changes': result['scheduler_changed_count'],
           'representatives': len(selected), 'identity_pairs': len(divergences), 'new_physics_episodes': 0})


if __name__ == '__main__':
    main()
