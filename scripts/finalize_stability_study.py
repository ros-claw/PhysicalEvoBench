"""Wait for real physics, then audit and package; never changes or extends the study."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from physicalevobench.adapters.arena_worker import arena_python_path
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    p.add_argument('--evidence', required=True)
    p.add_argument('--verify-output', required=True)
    p.add_argument('--log-dir', required=True)
    p.add_argument('--report', default='docs/experiments/STABILITY_RESULTS_20261024.md')
    p.add_argument('--wait', action='store_true')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    out, logs = Path(a.run_dir).absolute(), Path(a.log_dir).absolute()
    logs.mkdir(parents=True, exist_ok=False)
    save_json(logs/'request.json', {'argv': sys.argv, 'started_at': now(),
                                  'note': 'audit-only pipeline; zero additional physics episodes'})
    try:
        while True:
            try:
                status = json.loads((out/'status.json').read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                status = None
            if status:
                if status['status'] != 'COMPLETED':
                    raise RuntimeError(f'Physical study did not complete: {status}')
                break
            if not a.wait:
                raise RuntimeError('Physical study is still running')
            time.sleep(10)
        if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
            raise RuntimeError('Commit final delivery source before processing')
        save_json(logs/'source.json', {'source_commit': command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout'],
                                       'processing_started_at': now()})
        native = str(arena_python_path({}, root/'external/IsaacLab-Arena'))
        cpu_environment = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONPATH=str(root))
        steps = [
            ('models', [native, 'scripts/audit_stability_models.py', '--run-dir', str(out)]),
            ('study', [sys.executable, 'scripts/audit_stability_study.py', '--run-dir', str(out)]),
            ('diagnostics', [sys.executable, 'scripts/diagnose_stability_study.py', '--run-dir', str(out)]),
            ('report', [sys.executable, 'scripts/report_stability_study.py', '--run-dir', str(out), '--output', a.report]),
            ('package', [sys.executable, 'scripts/package_stability_study.py', '--run-dir', str(out), '--output', a.evidence]),
            ('public_verify', [sys.executable, 'scripts/verify_stability_delivery.py', '--evidence', a.evidence,
                               '--output', a.verify_output, '--numpy-python', native]),
        ]
        for name, argv in steps:
            save_json(logs/(name+'-launch.json'), {'argv': argv, 'started_at': now()})
            with (logs/(name+'.log')).open('w') as log:
                code = subprocess.run(argv, cwd=root, env=cpu_environment, stdout=log,
                                      stderr=subprocess.STDOUT, timeout=3600).returncode
            save_json(logs/(name+'-process.json'), {'returncode': code, 'finished_at': now()})
            if code:
                raise RuntimeError(f'Delivery stage failed: {name}; inspect {logs}')
        save_json(logs/'status.json', {'status': 'COMPLETED', 'finished_at': now(),
                                     'scientific_outcome': json.loads((out/'results.json').read_text())['status']})
    except Exception as error:
        save_json(logs/'status.json', {'status': 'FAILED', 'error': str(error), 'at': now()})
        raise


if __name__ == '__main__':
    main()
