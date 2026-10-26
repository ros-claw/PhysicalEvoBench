"""Bounded, budget-reserved native diagnostic worker, never learner training."""

import argparse
import gzip
import json
import shutil
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.confirmation import now


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    out = Path(p.parse_args().run_dir)
    cfg = json.loads((out/'config.json').read_text())
    if len(cfg['jobs']) != cfg['physical_budget']:
        raise ValueError('Reserve exact diagnostic budget')
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app = get_isaaclab_arena_cli_parser().parse_args(['--device', 'cuda:0'])
    with SimulationAppContext(app):
        from physicalevobench.protocols.skill import SkillSpec
        from physicalevobench.v02.native import DiagnosticWorker

        if sha256(cfg['checkpoint_path']) != cfg['checkpoint_sha256']:
            raise ValueError('Diagnostic model hash mismatch')
        if cfg.get('policy_config_sha256') and sha256(Path(cfg['checkpoint_path']).parent/'params/agent.yaml') != cfg['policy_config_sha256']:
            raise ValueError('Registered inference policy configuration changed')
        if cfg.get('policy_config_sha256'):
            shutil.copyfile(Path(cfg['checkpoint_path']).parent/'params/agent.yaml', out/'policy_config.yaml')
        worker = DiagnosticWorker(cfg['checkpoint_path'], out, cfg)
        if cfg.get('reference_controller'):
            from physicalevobench.calibration.policies import GeometryExpert, OpenGripper

            if cfg['reference_controller'] == 'GeometryExpert':
                worker.policy = GeometryExpert(worker)
            elif cfg['reference_controller'] == 'OpenGripper':
                worker.policy = OpenGripper(worker.policy, worker.action_mapping['gripper_action']['start'])
            elif cfg['reference_controller'] != 'Original':
                raise ValueError('Unknown calibrated reference attempt')
            # Keep proposal capture at the outer policy boundary, including the
            # expert/negative control. No evaluator or physics changes here.
            policy_action = worker.policy.get_action

            def propose(env, observation):
                value = policy_action(env, observation)
                worker.last_network_proposal = value.clone()
                return value

            worker.policy.get_action = propose
        ledger, rows = [], []
        try:
            for job in cfg['jobs']:
                ledger.append({'episode_id': job['episode_id'], 'reserved_at': now()})
                save_json(out/'budget_ledger.json', ledger)
                row = worker.run_episode(job['condition'], SkillSpec(worker.checkpoint_hash), 'v02-diagnostic', job['episode_id'])
                trace = out/row['trace_artifact']
                with trace.open('rb') as src, gzip.open(str(trace)+'.gz', 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                trace.unlink()
                row['trace_artifact'] += '.gz'
                row['trace_sha256'] = sha256(out/row['trace_artifact'])
                save_json(out/'episodes'/job['episode_id']/'episode.json', row)
                rows.append(row)
                (out/'episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            save_json(out/'status.json', {'status': 'COMPLETED', 'episodes': len(rows)})
        except Exception as error:
            save_json(out/'status.json', {'status': 'INFRA_FAILURE', 'episodes': len(rows), 'error': str(error)})
            raise
        finally:
            worker.close()


if __name__ == '__main__':
    main()
