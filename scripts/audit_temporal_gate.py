"""Recheck the selected candidate, all paired raw traces and the validation decision."""

import argparse
import json
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.audit import near, read_jsonl
from physicalevobench.evaluation.confirmation_audit import load
from physicalevobench.evaluation.temporal_audit import audit_temporal_episode
from physicalevobench.protocols.temporal_skill import TemporalSkill
from physicalevobench.protocols.guarded_skill import GuardedSkill


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-dir',required=True)
    parser.add_argument('--exploration',required=True)
    args=parser.parse_args()
    root=Path(args.run_dir).absolute()
    exploration=Path(args.exploration).absolute()
    cfg=load(root/'config.json')
    if cfg['training_selection_sha256']!=sha256(exploration/'training_selection.json'):
        raise ValueError('Training selection changed after gate registration')
    if cfg['selected_skill']!=load(exploration/'training_selection.json')['selected']['skill']:
        raise ValueError('Validation candidate differs from training selection')
    rows,ledger=read_jsonl(root/'episodes.jsonl'),load(root/'budget_ledger.json')
    if load(root/'status.json')['status']!='VALIDATION_COMPLETED' or len(rows)!=32:
        raise ValueError('Incomplete validation')
    if [r['episode_id'] for r in rows]!=[r['episode_id'] for r in ledger] or [r['used'] for r in ledger]!=list(range(1,33)):
        raise ValueError('Invalid validation budget ledger')
    mapping=load(root/'action_mapping.json')
    registry={c['condition_id']:c for c in cfg['conditions']}
    if len(registry)!=16 or len({c['seed'] for c in registry.values()})!=16:
        raise ValueError('Validation conditions overlap')
    train_seeds={c['seed'] for c in load(exploration/'registration.json')['conditions']}
    if train_seeds & {c['seed'] for c in registry.values()}:
        raise ValueError('Validation seed leaked from training')
    previous={}
    for row in rows:
        if row['split']!='validation':
            raise ValueError('Wrong validation split')
        initial=audit_temporal_episode(root,row,registry[row['condition_id']],mapping)
        prior=previous.setdefault(row['condition_id'],initial)
        for key in ('joint_position','object_position','object_orientation','target_command','inertia_readback'):
            if not near(prior[key],initial[key]):
                raise ValueError('Initial state pairing failed')
    groups={arm:[r for r in rows if r['agent_id']==arm] for arm in ('original','candidate')}
    skill_type=GuardedSkill if cfg['selected_skill']['schema_version']=='guarded-1' else TemporalSkill
    baseline=skill_type(cfg['checkpoint_sha256'])
    candidate=skill_type.from_dict(cfg['selected_skill'])
    for arm,skill in [('original',baseline),('candidate',candidate)]:
        if len(groups[arm])!=16 or {r['condition_id'] for r in groups[arm]}!=registry.keys():
            raise ValueError('Incomplete paired validation coverage')
        if any(r['skill_sha256']!=skill.sha256 for r in groups[arm]):
            raise ValueError('Validation skill changed')
    scores={arm:sum(r['success'] for r in group) for arm,group in groups.items()}
    joints={arm:sum(r['joint_limit_violation_count'] for r in group) for arm,group in groups.items()}
    promote=scores['candidate']>scores['original'] and joints['candidate']<=joints['original']
    decision=load(root/'decision.json')
    if (decision['decision']!=('promote' if promote else 'rollback')
            or decision['original_successes']!=scores['original']
            or decision['candidate_successes']!=scores['candidate']
            or decision['retained_skill']!=(candidate if promote else baseline).to_dict()):
        raise ValueError('Stored gate decision differs from independent calculation')
    save_json(root/'audit.json',{'status':'PASS','physical_episodes_verified':32,
              'paired_validation_conditions':16,'heldout_test_episodes':0,
              'recomputed_successes':scores,'recomputed_joint_limit_samples':joints})
    print(json.dumps(decision,indent=2))


if __name__=='__main__':
    main()
