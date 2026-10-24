"""Separate PPO process; receives public training transitions over a local RPC."""

import argparse
import copy
import json
from multiprocessing.connection import Client
from pathlib import Path

import numpy as np
import torch
import yaml
from tensordict import TensorDict
from rsl_rl.runners import OnPolicyRunner

from physicalevobench.doctor import save_json, sha256
from physicalevobench.calibration.public_schema import learner_feedback


class PublicTrainingEnv:
    def __init__(self, connection, hello):
        if set(hello) != {'observations', 'num_envs', 'num_actions', 'max_episode_length'}:
            raise ValueError('Unexpected training handshake fields')
        self.connection = connection
        self.num_envs, self.num_actions = hello['num_envs'], hello['num_actions']
        self.max_episode_length = hello['max_episode_length']
        self.device = 'cuda:0'
        self.cfg = {'public_observation_groups': ['policy', 'task_obs']}
        self.obs = self.convert(hello['observations'])
        self.episode_length_buf = torch.zeros(self.num_envs, device=self.device, dtype=torch.long)

    def convert(self, values):
        if set(values) != {'policy', 'task_obs'}:
            raise ValueError('Only public observation groups allowed')
        return TensorDict({k:torch.as_tensor(v.copy(), device=self.device) for k,v in values.items()},
                          batch_size=[self.num_envs])

    def get_observations(self):
        return self.obs

    def step(self, actions):
        self.connection.send({'actions': actions.detach().cpu().numpy()})
        data = learner_feedback(self.connection.recv())
        self.obs = self.convert(data['observations'])
        rewards = torch.as_tensor(data['rewards'].copy(), device=self.device)
        dones = torch.as_tensor(data['dones'].copy(), device=self.device)
        self.episode_length_buf += 1
        self.episode_length_buf[dones.bool()] = 0
        return self.obs, rewards, dones, {'time_outs':torch.as_tensor(data['time_outs'].copy(), device=self.device)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--socket', required=True)
    p.add_argument('--config', required=True)
    args = p.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    if set(cfg) not in ({'checkpoint', 'output', 'learner_seed', 'iterations'},
                        {'checkpoint', 'output', 'learner_seed', 'iterations', 'learning_rate'}):
        raise ValueError('Learner config contains evaluator fields')
    torch.set_num_threads(4)
    torch.manual_seed(cfg['learner_seed'])
    np.random.seed(cfg['learner_seed'] % (2**32))
    conn = Client(args.socket, family='AF_UNIX')
    env = PublicTrainingEnv(conn, conn.recv())
    checkpoint = Path(cfg['checkpoint'])
    agent = yaml.safe_load((checkpoint.parent/'params/agent.yaml').read_text())
    agent['device'] = 'cuda:0'
    runner = OnPolicyRunner(env, copy.deepcopy(agent), log_dir=None, device='cuda:0')
    runner.load(str(checkpoint))
    if 'learning_rate' in cfg:
        rate = cfg['learning_rate']
        if not 1e-5 <= rate <= 1e-4:
            raise ValueError('Learning rate outside registered bounds')
        runner.alg.learning_rate = rate
        runner.alg.schedule = 'fixed'
        for group in runner.alg.optimizer.param_groups:
            group['lr'] = rate
    before = {k:v.detach().cpu().clone() for k,v in runner.alg.get_policy().state_dict().items()}
    losses = []
    rewards = []
    step = env.step

    def logged_step(actions):
        result = step(actions)
        rewards.append(float(result[1].mean()))
        return result

    env.step = logged_step
    update = runner.alg.update

    def logged_update():
        loss = update()
        losses.append({k:float(v) for k,v in loss.items()})
        save_json(Path(cfg['output']).parent/'training_losses.json', losses)
        print(json.dumps({'iteration':len(losses), 'loss':loss}), flush=True)
        return loss

    runner.alg.update = logged_update
    runner.learn(cfg['iterations'])
    output = Path(cfg['output'])
    output.parent.mkdir(parents=True, exist_ok=True)
    (output.parent/'params').mkdir(exist_ok=True)
    (output.parent/'params/agent.yaml').write_text(yaml.safe_dump(agent))
    runner.save(str(output))
    after = runner.alg.get_policy().state_dict()
    norms = {k:float((after[k].detach().cpu()-v).norm()) for k,v in before.items() if v.is_floating_point()}
    save_json(output.parent/'weight_change.json', {'actor_parameter_change_norms':norms,
              'actor_changed':any(v > 0 for v in norms.values()), 'original_sha256':sha256(checkpoint),
              'candidate_sha256':sha256(output), 'iterations':len(losses)})
    if 'learning_rate' in cfg:
        from physicalevobench.stability.metrics import train_recipe

        save_json(output.parent/'public_reward_means.json', rewards)
        save_json(output.parent/'next_recipe.json', train_recipe(rewards, cfg['learning_rate']))
    conn.send({'finished':True, 'candidate_sha256':sha256(output)})
    conn.close()


if __name__ == '__main__':
    main()
