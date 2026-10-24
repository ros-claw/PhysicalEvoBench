"""Independent CPU re-audit of archived transitions and actual model tensors.

Run with Arena's pinned interpreter for NumPy/Torch, without starting Isaac Sim.
"""

import argparse
import json
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.calibration.public_schema import exact_fields


def main():
    import numpy as np
    import torch

    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    a=p.parse_args()
    out=Path(a.run_dir)
    def load(path):
        return json.loads(path.read_text())
    cfg=load(out/'config.json')
    archive=load(out/'training_archive.json')
    request=load(out/'learner_request.json')
    fields = ('checkpoint','output','learner_seed','iterations')
    exact_fields(request, fields + (('learning_rate',) if cfg.get('stability_study') else ()))
    ledger=[json.loads(x) for x in (out/'budget_ledger.jsonl').read_text().splitlines()]
    if len(ledger)!=cfg['iterations']*24 or any(r['reserved_transitions']!=(i+1)*cfg['num_envs'] for i,r in enumerate(ledger)):
        raise ValueError('Training reservation ledger mismatch')
    transitions=done=0
    reward_min, reward_max, action_max = float('inf'), -float('inf'), 0.
    previous=None
    reward_means=[]
    unfinished_lengths=np.zeros(cfg['num_envs'], dtype=np.int64)
    for chunk in archive['chunks']:
        path=out/chunk['path']
        if sha256(path)!=chunk['sha256']:
            raise ValueError('Training transition archive digest mismatch')
        with np.load(path,allow_pickle=False) as packed:
            data = {k: packed[k] for k in packed.files}
            if cfg.get('stability_study'):
                for group in ('policy','task_obs'):
                    stream = data.pop('stream_'+group)
                    if stream.shape[0] != 25:
                        raise ValueError('Compact observation stream length mismatch')
                    data['before_'+group], data['after_'+group] = stream[:-1], stream[1:]
            expected={'before_policy','before_task_obs','actions','rewards','dones','time_outs',
                      'after_policy','after_task_obs','evaluator_mass'}
            if set(data)!=expected or data['actions'].shape!=(24,cfg['num_envs'],8):
                raise ValueError('Transition shape/fields mismatch')
            for k in data:
                if not np.isfinite(data[k]).all():
                    raise ValueError('Nonfinite training data')
            reward_min=min(reward_min,float(data['rewards'].min()))
            reward_means.extend(float(row.mean()) for row in data['rewards'])
            reward_max=max(reward_max,float(data['rewards'].max()))
            action_max=max(action_max,float(np.abs(data['actions']).max()))
            mass=data['evaluator_mass']
            if mass.min()<.8-1e-6 or mass.max()>3.2+1e-6:
                raise ValueError('Training mass outside registered range')
            for group in ('policy','task_obs'):
                if not np.array_equal(data['before_'+group][1:],data['after_'+group][:-1]):
                    raise ValueError('Training observation continuity failed')
                if previous is not None and not np.array_equal(previous[group],data['before_'+group][0]):
                    raise ValueError('Training chunk continuity failed')
            previous={group:data['after_'+group][-1].copy() for group in ('policy','task_obs')}
            transitions+=data['actions'].shape[0]*data['actions'].shape[1]
            done+=int(data['dones'].sum())
            for terminal in data['dones']:
                unfinished_lengths+=1
                unfinished_lengths[terminal.astype(bool)]=0
    if transitions!=cfg['transition_budget'] or transitions!=archive['transitions'] or done!=archive['completed_training_episodes']:
        raise ValueError('Training cost/completion count mismatch')
    official=[json.loads(line) for line in (out/'training_episodes.jsonl').read_text().splitlines()]
    completed=[row for row in official if row.get('episode_length',0)>0]
    completed_steps=sum(row['episode_length'] for row in completed)
    if len(completed)!=done or completed_steps+int(unfinished_lengths.sum())!=transitions:
        raise ValueError('Official training episode lengths plus unfinished rollouts do not cover transition budget')
    original=torch.load(request['checkpoint'],map_location='cpu',weights_only=False)
    candidate=torch.load(request['output'],map_location='cpu',weights_only=False)
    norms={k:float((candidate['actor_state_dict'][k]-v).norm())
           for k,v in original['actor_state_dict'].items() if v.is_floating_point()}
    freeze=load(out/'freeze.json')
    if not any(v>0 for v in norms.values()) or sha256(request['output'])!=freeze['candidate_sha256']:
        raise ValueError('No frozen actual model change')
    if sha256(request['checkpoint'])!=cfg['checkpoint_sha256']:
        raise ValueError('Original model changed')
    losses=load(Path(request['output']).parent/'training_losses.json')
    if len(losses)!=cfg['iterations'] or not all(np.isfinite(list(row.values())).all() for row in losses):
        raise ValueError('Missing or nonfinite optimizer updates')
    if cfg.get('stability_study'):
        from physicalevobench.stability.metrics import train_recipe

        public_rewards=load(Path(request['output']).parent/'public_reward_means.json')
        if not np.allclose(public_rewards,reward_means,rtol=1e-6,atol=1e-7):
            raise ValueError('Public reward summary differs from archived training rewards')
        if load(Path(request['output']).parent/'next_recipe.json') != train_recipe(public_rewards,request['learning_rate']):
            raise ValueError('Train-only scheduler decision mismatch')
    result={'reward_min':reward_min,'reward_max':reward_max,'maximum_action_abs':action_max,
            'status':'PASS','transitions':transitions,'completed_training_episodes':done,
            'unfinished_rollout_steps':int(unfinished_lengths.sum()),'completed_episode_steps':completed_steps,
            'optimizer_iterations':len(losses),'actor_changed':True,
            'actor_parameter_change_norms':norms,'candidate_sha256':sha256(request['output']),
            'learner_request_fields':list(request),'learner_feedback_fields':['observations','rewards','dones','time_outs'],
            'scope':'train-only payload contract and actual weight update; no improvement claim'}
    save_json(out/'audit.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
