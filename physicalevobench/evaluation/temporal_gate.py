"""Prospective 16-pair validation gate for a training-selected temporal skill."""

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
        skills = {'original': TemporalSkill(worker.checkpoint_hash),
                  'candidate': TemporalSkill.from_dict(config['selected_skill'])}
        rows, ledger = [], []
        rng = random.Random(202610221201)
        try:
            for i, condition in enumerate(config['conditions']):
                if i % 2 == 0:
                    order = list(skills)
                    rng.shuffle(order)
                for arm in order if i % 2 == 0 else list(reversed(order)):
                    if len(ledger) >= 32:
                        raise RuntimeError('Validation physical budget exhausted')
                    eid = f"{arm}-{condition['condition_id']}"
                    ledger.append({'episode_id':eid, 'split':'validation', 'used':len(ledger)+1,
                                   'reserved_at':now()})
                    save_json(output/'budget_ledger.json',ledger)
                    rows.append(worker.run_episode(condition,skills[arm],arm,eid))
                    (output/'episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            old = [r for r in rows if r['agent_id']=='original']
            new = [r for r in rows if r['agent_id']=='candidate']
            success_old, success_new = sum(r['success'] for r in old), sum(r['success'] for r in new)
            joint_old = sum(r['joint_limit_violation_count'] for r in old)
            joint_new = sum(r['joint_limit_violation_count'] for r in new)
            promote = success_new > success_old and joint_new <= joint_old
            if len(rows)!=32 or not any(r['maximum_action_change_abs']>0 for r in new):
                raise RuntimeError('Incomplete gate or identity candidate')
            save_json(output/'decision.json',{'decision':'promote' if promote else 'rollback',
                      'original_successes':success_old,'candidate_successes':success_new,
                      'original_joint_limit_samples':joint_old,'candidate_joint_limit_samples':joint_new,
                      'retained_skill':skills['candidate' if promote else 'original'].to_dict(),
                      'scope':'validation only; heldout efficacy NOT_TESTED'})
            save_json(output/'status.json',{'status':'VALIDATION_COMPLETED','physical_episodes':32})
        except Exception as error:
            save_json(output/'status.json',{'status':'INFRA_FAILURE','error':str(error)})
            raise
        finally:
            worker.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
