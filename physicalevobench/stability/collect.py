"""One immutable policy per native environment process; full-horizon evaluation."""

import argparse
import gzip
import json
import shutil
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.protocols.skill import SkillSpec


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    out = Path(p.parse_args().run_dir)
    cfg = json.loads((out/'config.json').read_text())
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app = get_isaaclab_arena_cli_parser().parse_args(['--device', 'cuda:0'])
    with SimulationAppContext(app):
        from physicalevobench.adapters.lift_worker import LiftWorker

        if sha256(cfg['checkpoint_path']) != cfg['checkpoint_sha256']:
            raise ValueError('Frozen model digest mismatch')
        worker = LiftWorker(cfg['checkpoint_path'], out, stability_mode=True)
        rows, ledger = [], []
        try:
            for job in cfg['jobs']:
                if len(ledger) >= cfg['physical_budget']:
                    raise ValueError('Episode budget exhausted')
                ledger.append({'episode_id': job['episode_id'], 'reserved_at': now()})
                save_json(out/'budget_ledger.json', ledger)
                row = worker.run_episode(job['condition'], SkillSpec(worker.checkpoint_hash),
                                         cfg['arm'], job['episode_id'])
                directory = out/'episodes'/job['episode_id']
                row['safety'] = json.loads((directory/'sampled_safety.json').read_text())
                # Lossless compression of the newly created trace, never a replacement of evidence.
                trace = directory/'trace.jsonl'
                with trace.open('rb') as src, gzip.open(str(trace)+'.gz', 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                trace.unlink()
                row['trace_artifact'] += '.gz'
                row['trace_sha256'] = sha256(out/row['trace_artifact'])
                save_json(directory/'episode.json', row)
                rows.append(row)
                (out/'episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            save_json(out/'status.json', {'status': 'COMPLETED', 'episodes': len(rows)})
        except Exception as error:
            save_json(out/'status.json', {'status': 'INFRA_FAILURE', 'error': str(error),
                                         'episodes': len(rows)})
            raise
        finally:
            worker.close()


if __name__ == '__main__':
    main()
