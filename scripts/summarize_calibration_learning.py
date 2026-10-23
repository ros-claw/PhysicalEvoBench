"""Build a source-backed study readout after every registered physical job completes."""

import argparse
import json
import random
from pathlib import Path

from physicalevobench.calibration.audit import lines, load
from physicalevobench.calibration.power import paired_power
from physicalevobench.doctor import save_json
from physicalevobench.evaluation.confirmation_stats import exact_p


NAMES={
    'measurement':'calibration-measurement-20261023-002',
    'expert_v1':'calibration-expert-pilot-20261023-002',
    'expert_v2':'calibration-expert-v2-pilot-20261023-001',
    'expert_v3':'calibration-expert-v3-pilot-20261023-001',
    'expert_test':'calibration-expert-test-20261023-001',
    'persistent':'calibration-replay-20261023-001',
    'fresh_exploratory':'calibration-replay-fresh-20261023-001',
    'fresh_frozen':'calibration-replay-fresh-frozen-20261023-001',
    'training':'calibration-ppo-train-20261023-002',
    'validation':'calibration-ppo-validation-20261023-002',
    'heldout':'calibration-ppo-heldout-20261023-001',
    'startup_probe':'calibration-startup-probe-20261023-001',
    'camera':'calibration-camera-demo-20261023-001',
}


def paired_statistics(rows):
    indexed={a:{r['condition_id']:r for r in rows if r['agent_id']==a} for a in ('original','candidate')}
    if indexed['original'].keys()!=indexed['candidate'].keys():
        raise ValueError('Unpaired learned-policy results')
    delta=[int(indexed['candidate'][k]['success'])-int(indexed['original'][k]['success']) for k in indexed['original']]
    rng=random.Random(20261022)
    boot=sorted(sum(rng.choices(delta,k=len(delta)))/len(delta) for _ in range(10000))
    return {'pairs':len(delta),'wins':delta.count(1),'losses':delta.count(-1),
            'success_rate_difference':sum(delta)/len(delta),
            'conditional_bootstrap_95':[boot[250],boot[9750]],
            'p_one_sided_exact':exact_p(delta.count(1),delta.count(-1)),
            'scope':'one learned snapshot; condition-level inference, no cross-learning-seed claim'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runs-root',default='runs')
    p.add_argument('--output',required=True)
    a=p.parse_args()
    root=Path(a.runs_root)
    audits={key:load(root/name/'audit.json') for key,name in NAMES.items()}
    if any(audit['status']!='PASS' for audit in audits.values()):
        raise ValueError('Complete all raw artifact audits before summary')
    validation=root/NAMES['validation']
    heldout=root/NAMES['heldout']
    decision=load(validation/'decision.json')
    cfg=load(heldout/'config.json')
    if cfg['retention_decision']!=decision:
        raise ValueError('Heldout policy differs from frozen validation decision')
    train_cfg=load(root/NAMES['training']/'config.json')
    val_seeds={j['condition']['seed'] for j in load(validation/'config.json')['jobs']}
    test_seeds={j['condition']['seed'] for j in cfg['jobs']}
    if val_seeds & test_seeds or train_cfg['environment_seed'] in val_seeds|test_seeds:
        raise ValueError('Train/validation/heldout seed leakage')
    completed=sum(audit['physical_episodes'] for key,audit in audits.items() if key!='training')
    all_rows=lines(heldout/'episodes.jsonl')
    stats=paired_statistics(all_rows)
    result={'claim':'OBSERVED_SINGLE_SEED_HELDOUT_GAIN' if stats['success_rate_difference']>0 else 'NO_HELDOUT_IMPROVEMENT',
            'learning_seeds':1,'rounds':1,'completed_evaluation_and_diagnostic_episodes':completed,
            'completed_training_episodes':audits['training']['completed_training_episodes'],
            'training_transitions':audits['training']['transitions'],
            'training_completed_episode_steps':audits['training']['completed_episode_steps'],
            'training_unfinished_rollout_steps':audits['training']['unfinished_rollout_steps'],
            'training_active_unfinished_rollouts':train_cfg['num_envs'],
            'validation_decision':decision['decision'],'heldout_statistics':stats,
            'hypothetical_power':{str(n):paired_power(n,.1,.3) for n in (24,32,72,128,256)},
            'audits':audits,'robust_self_evolution':'NOT_ESTABLISHED',
            'limitations':['one learning seed and one update round','no equal-training-budget competing learner',
                'official success is instantaneous, no stable grasp/hold guarantee',
                'some per-finger maximum limit depths worsened despite lower historical aggregate count',
                'geometry expert failed; do not call it a successful strong-expert control',
                'two first-episode free falls were not reproduced in the targeted probe; cause unresolved',
                'camera replay becomes dark during the learned policy; outcome verified from physics traces'],
            'weights':'original and trained checkpoint stored outside repository; separate inherited licensing'}
    save_json(a.output,result)
    print(json.dumps({k:v for k,v in result.items() if k!='audits'},indent=2))


if __name__=='__main__':
    main()
