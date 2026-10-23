"""Native calibration worker. The supervisor writes a finite ordered job list first."""

import argparse
import json
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.protocols.skill import SkillSpec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True)
    args = parser.parse_args()
    out = Path(args.run_dir).absolute()
    cfg = json.loads((out / 'config.json').read_text())
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app = get_isaaclab_arena_cli_parser().parse_args(['--device', 'cuda:0'])
    with SimulationAppContext(app):
        from physicalevobench.adapters.lift_worker import LiftWorker
        from physicalevobench.calibration.policies import GeometryExpert, OpenGripper
        from isaaclab_arena.policy.rsl_rl_action_policy import RslRlActionPolicy, RslRlActionPolicyCfg

        worker = LiftWorker(Path(cfg['checkpoint_path']).expanduser(), out)
        original = worker.policy
        policies = {'original': original,
                    'open_gripper': OpenGripper(original, worker.action_mapping['gripper_action']['start']),
                    'expert': GeometryExpert(worker)}
        for name, path in cfg.get('additional_checkpoints', {}).items():
            policies[name] = RslRlActionPolicy(RslRlActionPolicyCfg(checkpoint_path=path, device='cuda:0'))
        ledger, rows = [], []
        try:
            for job in cfg['jobs']:
                if len(ledger) >= cfg['physical_budget']:
                    raise RuntimeError('Calibration physical budget exhausted')
                ledger.append({'episode_id': job['episode_id'], 'reserved_at': now(), 'used': len(ledger)+1})
                save_json(out / 'budget_ledger.json', ledger)
                name = job['policy']
                worker.policy = policies[name]
                worker.checkpoint = Path(cfg.get('additional_checkpoints', {}).get(name, cfg['checkpoint_path'])).expanduser()
                worker.checkpoint_hash = sha256(worker.checkpoint)
                row = worker.run_episode(job['condition'], SkillSpec(worker.checkpoint_hash), name, job['episode_id'])
                row.update(calibration_policy=name, policy_definition_sha256=cfg['policy_source_sha256'],
                           original_checkpoint_sha256=cfg['checkpoint_sha256'])
                save_json(out / 'episodes' / job['episode_id'] / 'episode.json', row)
                rows.append(row)
                (out/'episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            save_json(out/'status.json', {'status': 'COMPLETED', 'physical_episodes': len(rows)})
        except Exception as error:
            save_json(out/'status.json', {'status':'INFRA_FAILURE', 'error':str(error), 'physical_episodes':len(rows)})
            raise
        finally:
            worker.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
