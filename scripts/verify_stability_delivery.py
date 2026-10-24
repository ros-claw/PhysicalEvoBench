"""Verify a delivered archive from scratch, without licensed model weights."""

import argparse
import json
import os
import subprocess
import tarfile
from pathlib import Path

from audit_stability_study import verify

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import assert_pairs, audit_worker, read, rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--numpy-python', help='Interpreter with NumPy for complete public transition-value audit')
    a = p.parse_args()
    evidence, out = Path(a.evidence).absolute(), Path(a.output).absolute()
    out.mkdir(parents=True, exist_ok=False)
    for name, digest in read(evidence/'SHA256SUMS.json').items():
        if Path(name).name != name or sha256(evidence/name) != digest:
            raise ValueError('Delivery archive digest mismatch')
    manifest = read(evidence/'manifest.json')
    for path in sorted(evidence.glob('evidence-*.tar.gz')):
        with tarfile.open(path) as archive:
            archive.extractall(out, filter='data')
    for entry in manifest['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unexpected manifest path')
        path = out/relative
        if not path.is_file() or path.stat().st_size != entry['size'] or sha256(path) != entry['sha256']:
            raise ValueError('Raw delivered file digest mismatch')
    for ref in manifest['source_commits']:
        with tarfile.open(evidence/f'source-{ref}.tar.gz') as archive:
            archive.extractall(out/'sources'/ref, filter='data')
    checked_sources, failed_diagnostics, studies, calibrations = 0, 0, [], []
    for registration in sorted(out.glob('*/registration.json')):
        reg = read(registration)
        for name, digest in reg['source_sha256'].items():
            if sha256(out/'sources'/reg['source_commit']/name) != digest:
                raise ValueError('Registered source snapshot mismatch')
            checked_sources += 1
        if 'criteria' in reg and 'conditions' in reg:
            pairs = {arm: [] for arm in ('original', 'open_gripper')}
            for cfg in sorted(registration.parent.glob('*/config.json')):
                arm = read(cfg)['arm']
                pairs[arm].extend((r, cfg.parent) for r in audit_worker(cfg.parent))
            assert_pairs(pairs['original'], pairs['open_gripper'])
            expected = [c['condition_id'] for c in reg['conditions']]
            if any([r['condition_id'] for r, _ in data] != expected for data in pairs.values()):
                raise ValueError('Calibration conditions differ from registration')
            official = reg.get('primary_metric') == 'upstream_official_lift_success'
            counts = {arm: {'holding': None if official else sum(r['success'] for r, _ in data),
                            'instant': sum(r['success'] if official else r['stability']['instant_success'] for r, _ in data)}
                      for arm, data in pairs.items()}
            if official:
                passed = counts['original']['instant'] >= 10 and counts['open_gripper']['instant'] == 0
            else:
                passed = counts['original']['holding'] >= 8 and counts['original']['instant'] >= 10 and counts['open_gripper']['holding'] == 0
            stored = read(registration.parent/'results.json')
            if stored['counts'] != counts or stored['status'] != ('PASS' if passed else 'CALIBRATION_FAILED'):
                raise ValueError('Calibration outcome changed')
            calibrations.append({'study': registration.parent.name, 'status': stored['status'],
                                 'counts': counts, 'episodes': sum(map(len, pairs.values()))})
        elif read(registration.parent/'status.json')['status'] == 'COMPLETED':
            studies.append(verify(registration.parent))
        else:
            for worker in registration.parent.glob('preflight/block-*'):
                failed_diagnostics += len(audit_worker(worker))
    transition_audits = []
    if a.numpy_python:
        root = Path(__file__).resolve().parents[1]
        for archive in sorted(out.glob('*/s*-*/round-*/train/training_archive.json')):
            directory = archive.parent
            environment = dict(os.environ, PYTHONPATH=str(root))
            with (directory/'public_reaudit_console.log').open('w') as log:
                code = subprocess.run([a.numpy_python, '-m', 'physicalevobench.calibration.training_audit',
                                       '--public-data-only', '--run-dir', str(directory)],
                                      cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                      timeout=300).returncode
            if code:
                raise ValueError(f'Public numeric transition audit failed: {directory}')
            transition_audits.append({'path': str(directory.relative_to(out)),
                                      **read(directory/'public_transition_audit.json')})
    failed_training_episodes = sum(len([r for r in rows(p) if r.get('episode_length', 0) > 0])
                                  for p in out.glob('*/s*-*/round-*/train/training_episodes.jsonl'))
    result = {'status': 'PASS', 'raw_files': len(manifest['files']), 'source_hash_checks': checked_sources,
              'verifier_source_sha256': {str(path.relative_to(Path(__file__).resolve().parents[1])): sha256(path)
                                         for path in [Path(__file__).resolve(),
                                                      Path(__file__).with_name('audit_stability_study.py'),
                                                      *sorted((Path(__file__).resolve().parents[1]/'physicalevobench').rglob('*.py'))]},
              'completed_studies': studies, 'aborted_attempt_diagnostic_episodes': failed_diagnostics,
              'calibrations': calibrations, 'training_completed_episodes_from_raw_records': failed_training_episodes,
              'public_numeric_transition_audits': transition_audits,
              'private_tensor_audit': 'not rerun: separately licensed model files excluded',
              'training_transition_values': ('NUMERICALLY_RECOMPUTED' if a.numpy_python else 'archive hashes verified; supply --numpy-python to recompute values'),
              'scope': 'independent extraction and full raw evaluation/study recomputation'}
    save_json(out/'public_delivery_audit.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
