"""Verify a delivered archive from scratch, without licensed model weights."""

import argparse
import json
import tarfile
from pathlib import Path

from audit_stability_study import verify

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import audit_worker, read


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
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
    checked_sources, failed_diagnostics, studies = 0, 0, []
    for registration in sorted(out.glob('peb-stability-*/registration.json')):
        reg = read(registration)
        for name, digest in reg['source_sha256'].items():
            if sha256(out/'sources'/reg['source_commit']/name) != digest:
                raise ValueError('Registered source snapshot mismatch')
            checked_sources += 1
        if read(registration.parent/'status.json')['status'] == 'COMPLETED':
            studies.append(verify(registration.parent))
        else:
            for worker in registration.parent.glob('preflight/block-*'):
                failed_diagnostics += len(audit_worker(worker))
    result = {'status': 'PASS', 'raw_files': len(manifest['files']), 'source_hash_checks': checked_sources,
              'completed_studies': studies, 'aborted_attempt_diagnostic_episodes': failed_diagnostics,
              'private_tensor_audit': 'not rerun: separately licensed model files excluded',
              'training_transition_values': 'archive hashes verified; private numeric audits preserved',
              'scope': 'independent extraction and full raw evaluation/study recomputation'}
    save_json(out/'public_delivery_audit.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
