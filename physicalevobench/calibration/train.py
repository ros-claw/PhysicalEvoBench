"""Trusted simulator collector for bounded train-only PPO, without test feedback."""

import argparse
import json
import subprocess
import sys
import hashlib
from multiprocessing.connection import Listener
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.confirmation import now


def public_observations(obs):
    return {k:obs[k].detach().cpu().numpy().copy() for k in ('policy', 'task_obs')}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    a = p.parse_args()
    out = Path(a.run_dir).absolute()
    cfg = json.loads((out/'config.json').read_text())
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app = get_isaaclab_arena_cli_parser().parse_args(['--device','cuda:0'])
    with SimulationAppContext(app):
        import numpy as np
        import torch
        from isaaclab_arena.environments.arena_env_builder import ArenaEnvBuilder
        from isaaclab_arena.environments.arena_env_builder_cfg import ArenaEnvBuilderCfg
        from isaaclab_arena.variations.object_mass_variation import ObjectMassVariationCfg
        from isaaclab_arena.variations.uniform_sampler import UniformSamplerCfg
        from isaaclab_arena_environments.lift_object_environment import LiftObjectEnvironment, LiftObjectEnvironmentCfg
        from physicalevobench.adapters.lift_worker import LiftWorker

        definition = LiftObjectEnvironment().build(LiftObjectEnvironmentCfg(rl_training_mode=True))
        variation = definition.scene.assets['dex_cube'].get_variation('mass')
        variation.apply_cfg(ObjectMassVariationCfg(sampler_cfg=UniformSamplerCfg(low=[.8], high=[3.2]),
                                                  recompute_inertia=True))
        variation.enable()
        env = ArenaEnvBuilder(definition, ArenaEnvBuilderCfg(
            num_envs=cfg['num_envs'], device='cuda:0', presets='physx', seed=cfg['environment_seed'],
            recorder_dataset_export_dir_path=str(out/'recorder'), recorder_dataset_filename='dataset')).make_registered()
        base = env.unwrapped
        base.episode_recorder.set_output_path(out/'training_episodes.jsonl')
        checkpoint = Path(cfg['checkpoint_path']).expanduser()
        candidate = Path(cfg['candidate_path']).expanduser()
        learner_cfg = {'checkpoint':str(checkpoint), 'output':str(candidate),
                       'learner_seed':cfg['learner_seed'], 'iterations':cfg['iterations']}
        if cfg.get('stability_study'):
            learner_cfg['learning_rate'] = cfg['learning_rate']
        save_json(out/'learner_request.json', learner_cfg)
        socket = '/tmp/peb-' + hashlib.sha256(str(out).encode()).hexdigest()[:24] + '.sock'
        # Only a local trusted child connects. This is not an adversarial security boundary.
        listener = Listener(socket, family='AF_UNIX')
        learner_log = (out/'learner_console.log').open('w')
        child = subprocess.Popen([sys.executable, '-m', 'physicalevobench.calibration.learner',
                                  '--socket',socket,'--config',str(out/'learner_request.json')],
                                 stdout=learner_log, stderr=subprocess.STDOUT)
        connection = None
        chunks, completed, reserved, consumed = [], 0, 0, 0
        (out/'transitions').mkdir()
        arrays = {}
        try:
            # Bound connection startup so learner import failures cannot hang physics forever.
            listener._listener._socket.settimeout(120)
            connection = listener.accept()
            with torch.inference_mode():
                obs, _ = env.reset(seed=cfg['environment_seed'])
                save_json(out/'initial_training_state.json', {
                    'mass':LiftWorker.as_torch(base.scene['dex_cube'].data.body_mass).tolist(),
                    'public_observations':{k:v.tolist() for k,v in public_observations(obs).items()}})
                connection.send({'observations':public_observations(obs), 'num_envs':cfg['num_envs'],
                                 'num_actions':base.action_manager.total_action_dim,
                                 'max_episode_length':base.max_episode_length})
                with (out/'budget_ledger.jsonl').open('w') as ledger:
                    for step in range(cfg['iterations']*24):
                        request = connection.recv()
                        if set(request) != {'actions'}:
                            raise ValueError('Only actions accepted from learner')
                        action = torch.as_tensor(request['actions'], device=base.device)
                        if action.shape != (cfg['num_envs'],8) or not torch.isfinite(action).all():
                            raise ValueError('Invalid learner action')
                        proposed = action.detach().cpu().numpy().copy()
                        if cfg.get('action_limit') is not None:
                            action = action.clamp(-cfg['action_limit'], cfg['action_limit'])
                        if reserved + cfg['num_envs'] > cfg['transition_budget']:
                            raise RuntimeError('Training transition budget exhausted')
                        reserved += cfg['num_envs']
                        ledger.write(json.dumps({'vector_step':step, 'reserved_transitions':reserved,
                                                'reserved_at':now()})+'\n')
                        ledger.flush()
                        before = public_observations(obs)
                        mass = LiftWorker.as_torch(base.scene['dex_cube'].data.body_mass).detach().cpu().numpy().copy()
                        obs, reward, term, trunc, _ = env.step(action)
                        consumed += cfg['num_envs']
                        dones = (term | trunc).to(torch.long)
                        completed += int(dones.sum())
                        response = {'observations':public_observations(obs),
                                    'rewards':reward.detach().cpu().numpy().copy(),
                                    'dones':dones.cpu().numpy().copy(), 'time_outs':trunc.cpu().numpy().copy()}
                        evidence = {'before_policy':before['policy'], 'before_task_obs':before['task_obs'],
                                    'actions':action.detach().cpu().numpy().copy(), 'rewards':response['rewards'],
                                    'dones':response['dones'], 'time_outs':response['time_outs'],
                                    'after_policy':response['observations']['policy'],
                                    'after_task_obs':response['observations']['task_obs'], 'evaluator_mass':mass}
                        if cfg.get('action_limit') is not None:
                            evidence['proposed_actions'] = proposed
                        for k,v in evidence.items():
                            arrays.setdefault(k,[]).append(v)
                        connection.send(response)
                        if (step+1) % 24 == 0:
                            path = out/'transitions'/f'iteration-{(step+1)//24:04d}.npz'
                            packed = {k:np.stack(v) for k,v in arrays.items()}
                            if cfg.get('stability_study'):
                                for group in ('policy', 'task_obs'):
                                    packed['stream_'+group] = np.concatenate([
                                        packed.pop('before_'+group)[:1], packed.pop('after_'+group)], axis=0)
                            np.savez_compressed(path, **packed)
                            arrays = {}
                            chunks.append({'path':str(path.relative_to(out)), 'sha256':sha256(path)})
                            save_json(out/'progress.json', {'vector_steps':step+1, 'transitions':consumed,
                                      'completed_training_episodes':completed, 'initial_rollouts':cfg['num_envs']})
                            print(json.dumps({'training_vector_steps':step+1,'completed_episodes':completed}), flush=True)
            result = connection.recv()
            if set(result) != {'finished','candidate_sha256'} or result['finished'] is not True:
                raise ValueError('Learner did not freeze checkpoint')
            code = child.wait(timeout=120)
            if code or sha256(candidate) != result['candidate_sha256']:
                raise ValueError('Learner completion/checkpoint mismatch')
            if sha256(checkpoint) != cfg['checkpoint_sha256']:
                raise ValueError('Original checkpoint was changed')
            save_json(out/'training_archive.json', {'chunks':chunks, 'transitions':consumed,
                      'reserved_transitions':reserved, 'completed_training_episodes':completed,
                      'unfinished_rollouts':cfg['num_envs'], 'initial_rollouts':cfg['num_envs'],
                      'note':'training-mode dense-reward episodes; not official evaluation successes'})
            save_json(out/'freeze.json', {**result,'checkpoint':str(candidate), 'frozen_at':now(),
                      'weight_change':json.loads((candidate.parent/'weight_change.json').read_text())})
            save_json(out/'status.json', {'status':'TRAINING_COMPLETED','transitions':consumed})
        except Exception as error:
            save_json(out/'status.json', {'status':'INFRA_FAILURE','error':str(error),
                      'reserved_transitions':reserved,'consumed_transitions':consumed,
                      'completed_training_episodes':completed})
            raise
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=30)
            save_json(out/'learner_process.json', {'returncode':child.returncode})
            if connection:
                connection.close()
            listener.close()
            learner_log.close()
            env.close()


if __name__ == '__main__':
    main()
