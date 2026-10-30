"""Standalone real T0 smoke: no old study directory or calibration receipt."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.pilot import worker_config
from physicalevobench.core.runtime import NativeSession
from physicalevobench.core.tasks import task
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import digest, load


def run(root, out, reference, gpu, seed=2026103001):
    definition = task('lift-regression', 'DEV')
    base = load(reference)
    cfg = worker_config(base, 1)
    if not Path(cfg['checkpoint_path']).is_file():
        raise FileNotFoundError('Missing environment: set PHYSICALEVOBENCH_CHECKPOINT')
    arena = root/'external/IsaacLab-Arena'
    if not (arena/'.venv/bin/python').exists():
        raise FileNotFoundError('Missing environment: install pinned Arena native runtime')
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit source before physical registration')
    source = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    out.mkdir(parents=True, exist_ok=False)
    job = {'episode_id': 'smoke-000', 'condition': {'condition_id': 'standalone-smoke',
           'split': 'development', 'seed': seed, 'object_mass_kg': .1},
           'reference_config': base['reference_config'],
           'identity': {'task_id': definition['task_version'], 'artifact_hash': digest(base)}}
    save_json(out/'registration.json', {'schema': 'core-standalone-smoke-1', 'at': now(),
              'mode': 'DEV', 'task': definition, 'source_commit': source, 'physical_budget': 1,
              'job': job, 'historical_study_dependency': None})
    session = NativeSession(root, out/'native', source, cfg, gpu)
    try:
        session.ready()
        row = session.trial(job)
    finally:
        session.close()
    data = audit_session(out/'native')
    result = {'status': 'PASS', 'physical_episodes': len(data), 'task_success': row['success'],
              'steps': row['steps'], 'scope': 'Physical execution only; no learning claim'}
    save_json(out/'result.json', result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--reference', default='configs/core/frozen_reference.json')
    p.add_argument('--gpu', type=int, default=2)
    p.add_argument('--seed', type=int, default=2026103001)
    a = p.parse_args()
    print(json.dumps(run(Path.cwd(), Path(a.output).absolute(), Path(a.reference), a.gpu, a.seed)))


if __name__ == '__main__':
    main()
