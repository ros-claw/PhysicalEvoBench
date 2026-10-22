"""Audit all exploration rollouts, then select solely from training evidence."""

import argparse
import json
from pathlib import Path

from physicalevobench.doctor import save_json
from physicalevobench.evaluation.audit import near, read_jsonl
from physicalevobench.evaluation.confirmation_audit import load
from physicalevobench.evaluation.temporal_audit import audit_temporal_episode
from physicalevobench.protocols.temporal_skill import TemporalSkill


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--study-dir', required=True)
    args = parser.parse_args()
    root = Path(args.study_dir).absolute()
    registration = load(root / 'registration.json')
    results, initial_states = [], {}
    baseline_rows = []
    for d in sorted(root.glob('group-*')):
        cfg = load(d / 'config.json')
        rows, ledger = read_jsonl(d / 'episodes.jsonl'), load(d / 'budget_ledger.json')
        if load(d / 'status.json')['status'] != 'EXPLORATION_COMPLETED' or len(rows) != 32:
            raise ValueError('Incomplete exploration')
        if [r['episode_id'] for r in rows] != [r['episode_id'] for r in ledger]:
            raise ValueError('Episode budget ledger mismatch')
        if [r['used'] for r in ledger] != list(range(1,33)):
            raise ValueError('Physical budget changed')
        registry = {c['condition_id']: c for c in registration['conditions']}
        mapping = load(d / 'action_mapping.json')
        for row in rows:
            if row['split'] != 'train':
                raise ValueError('Exploration may only consume training conditions')
            initial = audit_temporal_episode(d, row, registry[row['condition_id']], mapping)
            previous = initial_states.setdefault(row['condition_id'], initial)
            for key in ('joint_position', 'object_position', 'object_orientation', 'target_command', 'inertia_readback'):
                if not near(previous[key], initial[key]):
                    raise ValueError('Paired initial state mismatch')
        for name in cfg['trials']:
            group = [r for r in rows if r['agent_id']==name]
            if len(group) != 8 or {r['condition_id'] for r in group} != registry.keys():
                raise ValueError('Trial coverage mismatch')
            skill = TemporalSkill.from_dict(load(d / 'skills.json')[name])
            if any(r['skill_sha256'] != skill.sha256 for r in group):
                raise ValueError('Trial skill changed')
            if name == 'original':
                baseline_rows.extend(group)
                continue
            results.append({'trial': name, 'group': d.name, 'skill': skill.to_dict(),
                            'successes': sum(r['success'] for r in group), 'episodes': len(group),
                            'joint_limit_samples': sum(r['joint_limit_violation_count'] for r in group),
                            'maximum_action_change_abs': max(r['maximum_action_change_abs'] for r in group)})
    baseline_skill = TemporalSkill.from_dict(load(root / 'group-0/skills.json')['original'])
    original = {'trial': 'original', 'skill': baseline_skill.to_dict(),
                'successes': sum(r['success'] for r in baseline_rows)/3, 'episodes':8,
                'joint_limit_samples': sum(r['joint_limit_violation_count'] for r in baseline_rows)/3}
    def rank(r):
        s = r['skill']
        return (-r['successes'], r['joint_limit_samples'],
                abs(1-s['arm_smoothing_alpha'])+s['gripper_hold_steps']/250, r['trial'])
    candidates = sorted(results+[original],key=rank)
    selected = candidates[0]
    save_json(root / 'audit.json', {'status':'PASS','real_episodes_verified':96,
              'unique_training_conditions':8,'heldout_test_episodes':0,
              'control_reconstruction':'independent arithmetic from raw traces'})
    save_json(root / 'training_selection.json', {'selected':selected,'ranking':candidates,
              'original_replay_successes':sum(r['success'] for r in baseline_rows),
              'original_replay_episodes':24,'selection_uses':'training outcomes only',
              'heldout_claim':'NOT_TESTED'})
    print(json.dumps(load(root / 'training_selection.json'),indent=2))


if __name__ == '__main__':
    main()
