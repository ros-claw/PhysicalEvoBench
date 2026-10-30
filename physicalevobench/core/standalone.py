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


def run(root, out, reference, gpu, seed=2026103001, task_name='lift-regression', artifact_path=None):
    definition = task(task_name, 'DEV')
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
    program=None
    retained=None
    if task_name=='place-settle':
        from physicalevobench.core.execution_identity import validate_execution
        from physicalevobench.core.program import Program
        receipt=json.loads((root/'configs/learning/qualification.json').read_text())
        validate_execution(root,receipt,base)
        if artifact_path:
            from physicalevobench.core.artifact import load as load_artifact
            retained=load_artifact(artifact_path)
            if (retained['payload']['initial_reference']!=digest(base) or
                    retained['payload']['task']!=definition['task_version']):
                raise ValueError('Frozen artifact differs from public task/reference')
            program=Program.from_dict(retained['payload']['skill'])
        else:
            program=Program.from_dict(json.loads((root/'configs/learning/reference_aperture.json').read_text()))
        cfg.update(core_task='place',task_version=definition['task_version'],horizon_s=20.,
                   control_profile='contact-integral-v1',public_goal=[.62,.12,.021])
    elif artifact_path:
        raise ValueError('Program artifact requires --task place-settle')
    out.mkdir(parents=True, exist_ok=False)
    job = {'episode_id': 'smoke-000', 'condition': {'condition_id': 'standalone-smoke',
           'split': 'development', 'seed': seed, 'object_mass_kg': .1},
           'reference_config': base['reference_config'],
           'identity': {'task_id': definition['task_version'], 'artifact_hash': digest(base)}}
    if program is not None:
        job.update(program=program.to_dict(),public_goal=cfg['public_goal'])
        if retained:
            job['identity']['effective_artifact_hash']=retained['effective_artifact_hash']
            save_json(out/'imported_artifact.json',retained)
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
              'steps': row['steps'], 'scope': 'Frozen artifact physical execution only; no independent re-learning or learning-effect claim'}
    save_json(out/'result.json', result)
    save_json(out/'status.json',{'status':'COMPLETED','at':now(),'episodes':len(data)})
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--reference', default='configs/core/frozen_reference.json')
    p.add_argument('--gpu', type=int, default=2)
    p.add_argument('--seed', type=int, default=2026103001)
    p.add_argument('--task', default='lift-regression',choices=['lift-regression','place-settle'])
    p.add_argument('--artifact',help='Optional frozen graph artifact for place physical smoke')
    a = p.parse_args()
    print(json.dumps(run(Path.cwd(), Path(a.output).absolute(), Path(a.reference), a.gpu, a.seed,a.task,Path(a.artifact) if a.artifact else None)))


if __name__ == '__main__':
    main()
