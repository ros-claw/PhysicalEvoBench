"""Training-side temporal controller exploration; no heldout scores are produced."""

import argparse
import json
import random
from pathlib import Path

from physicalevobench.doctor import diagnose, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.protocols.temporal_skill import TemporalSkill


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True)
    args = parser.parse_args()
    output = Path(args.run_dir).absolute()
    config = json.loads((output / 'config.json').read_text())
    with (output / 'run.lock').open('x'):
        pass
    provenance = diagnose(config)
    root = Path(__file__).resolve().parents[2]
    provenance.update(started_at=now(), source_sha256={str(p.relative_to(root)): sha256(p)
                      for p in (root / 'physicalevobench').rglob('*.py')})
    save_json(output / 'provenance.json', provenance)
    if provenance['blockers']:
        raise RuntimeError(provenance['blockers'])
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app_args = get_isaaclab_arena_cli_parser().parse_args(['--device', 'cuda:0'])
    with SimulationAppContext(app_args):
        from physicalevobench.adapters.lift_worker import LiftWorker

        worker = LiftWorker(Path(config['checkpoint_path']).expanduser(), output)
        ledger, rows = [], []
        skills = {name: TemporalSkill(worker.checkpoint_hash, **params)
                  for name, params in config['trials'].items()}
        save_json(output / 'skills.json', {name: s.to_dict() for name, s in skills.items()})
        rng = random.Random(config['order_seed'])
        try:
            for condition in config['conditions']:
                order = list(skills)
                rng.shuffle(order)
                for name in order:
                    if len(ledger) >= config['physical_budget']:
                        raise RuntimeError('Exploration budget exceeded')
                    eid = f"{name}-{condition['condition_id']}"
                    ledger.append({'episode_id': eid, 'split': 'train', 'reserved_at': now(),
                                   'used': len(ledger) + 1})
                    save_json(output / 'budget_ledger.json', ledger)
                    row = worker.run_episode(condition, skills[name], name, eid)
                    rows.append(row)
                    (output / 'episodes.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            if len(rows) != config['physical_budget']:
                raise RuntimeError('Incomplete exploration')
            save_json(output / 'status.json', {'status': 'EXPLORATION_COMPLETED',
                      'episodes': len(rows), 'heldout_test_episodes': 0})
        except Exception as error:
            save_json(output / 'status.json', {'status': 'INFRA_FAILURE', 'error': str(error)})
            raise
        finally:
            worker.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
