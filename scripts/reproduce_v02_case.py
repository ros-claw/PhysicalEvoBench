"""Reproduce one registered case, using its immutable source and new budget.

This reruns physics; it never promises bitwise replay of the original result.
The separately licensed checkpoint must already exist on the local machine.
"""

import argparse
from pathlib import Path

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.stability.audit import read
from physicalevobench.stability.study import launch
from physicalevobench.v02.audit import audit_run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--registration', required=True)
    parser.add_argument('--worker', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--gpu', type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit reproduction launcher before spending physical budget')
    registration_path = Path(args.registration).absolute()
    original = read(registration_path)
    plans = [p for p in original['plans'] if p['name'] == args.worker]
    if original['schema'] != 'v02-diagnostics-1' or len(plans) != 1 or len(plans[0]['jobs']) != 1:
        raise ValueError('Choose one registered single-episode representative worker')
    plan = plans[0]
    if sha256(plan['checkpoint_path']) != plan['checkpoint_sha256']:
        raise ValueError('Local licensed model does not match registered SHA256')
    source, hashes = snapshot_source(root, original['source_commit'])
    if hashes != original['source_sha256']:
        raise ValueError('Runtime source differs from original registration')
    out = Path(args.output).absolute()
    out.mkdir(parents=True, exist_ok=False)
    save_json(out/'registration.json', {**original, 'phase': 'single_case_reproduction',
              'registered_at': now(), 'gpu': args.gpu, 'physical_budget': 1, 'plans': [plan], 'after': None,
              'reproduction_of': {'path': str(registration_path), 'sha256': sha256(registration_path)},
              'launcher_commit': command(['git','rev-parse','HEAD'],cwd=root)['stdout']})
    child = out/plan['name']
    child.mkdir()
    save_json(child/'config.json', plan)
    save_json(child/'worker_reservation.json', {'episodes': 1, 'reserved_at': now()})
    save_json(child/'gpu_workload.json', {'at': now(), 'exclusive': False,
              'query': command(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader'])})
    try:
        launch(root, source, child, 'physicalevobench.v02.collect', args.gpu)
        from physicalevobench.stability.audit import rows

        episodes = [{'worker':plan['name'], **r} for r in rows(child/'episodes.jsonl')]
        save_json(out/'results.json', {'episodes': episodes, 'count': len(episodes), 'learning_updates': 0})
        save_json(out/'status.json', {'status': 'COMPLETED', 'episodes': len(episodes), 'finished_at': now()})
        save_json(out/'audit.json', audit_run(out))
    except Exception as error:
        save_json(out/'status.json', {'status':'INFRA_FAILURE', 'error':str(error), 'at':now()})
        raise


if __name__ == '__main__':
    main()
