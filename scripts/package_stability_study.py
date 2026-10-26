"""Lossless evidence delivery, split below 48 MiB; never distributes model weights."""

import argparse
import io
import json
import subprocess
import tarfile
from pathlib import Path

from physicalevobench.doctor import save_json, sha256


def package(root, inputs, destination):
    destination.mkdir(parents=True, exist_ok=False)
    paths = []
    for study in inputs:
        for path in sorted(study.rglob('*')):
            if path.is_file() and path.suffix not in ('.pt', '.pth', '.hdf5'):
                if 'recorder' not in path.relative_to(study).parts:
                    paths.append((path, Path(study.name)/path.relative_to(study)))
    limit = 48*1024*1024
    groups, current, size = [], [], 0
    for item in paths:
        cost = item[0].stat().st_size
        if cost > limit:
            raise ValueError(f'Unexpected oversized evidence file: {item[0]}')
        if current and size+cost > limit:
            groups.append(current)
            current, size = [], 0
        current.append(item)
        size += cost
    if current:
        groups.append(current)
    manifest = []
    for index, group in enumerate(groups):
        target = destination/f'evidence-{index:03d}.tar.gz'
        with tarfile.open(target, 'w:gz') as archive:
            for path, name in group:
                archive.add(path, arcname=str(name), recursive=False)
                manifest.append({'path': str(name), 'sha256': sha256(path), 'size': path.stat().st_size})
    registered_refs = sorted({json.loads((study/'registration.json').read_text())['source_commit'] for study in inputs})
    launcher_refs = {json.loads((study/'registration.json').read_text()).get('launcher_commit') for study in inputs}
    launcher_refs.discard(None)
    delivery_ref = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    refs = sorted(set(registered_refs + [delivery_ref]) | launcher_refs)
    for ref in refs:
        data = subprocess.check_output(['git', 'archive', '--format=tar', ref,
                                        'physicalevobench', 'scripts', 'configs', 'docs/experiments',
                                        'AGENTS.md', 'LICENSE', 'NOTICE.md'], cwd=root)
        target = destination/f'source-{ref}.tar.gz'
        with tarfile.open(fileobj=io.BytesIO(data)) as original, tarfile.open(target, 'w:gz') as output:
            for member in original:
                output.addfile(member, original.extractfile(member) if member.isfile() else None)
    save_json(destination/'manifest.json', {'schema': 'stability-delivery-1', 'files': manifest,
                                          'source_commits': refs, 'registered_source_commits': registered_refs,
                                          'delivery_tool_source_commit': delivery_ref,
                                          'models': 'EXCLUDED_SEPARATE_NVIDIA_LICENSE'})
    checksums = {p.name: sha256(p) for p in sorted(destination.iterdir()) if p.is_file()}
    save_json(destination/'SHA256SUMS.json', checksums)
    return {'archives': len(groups), 'files': len(manifest), 'bytes': sum(p.stat().st_size for p in destination.iterdir())}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', action='append', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(package(Path(__file__).resolve().parents[1], [Path(s) for s in a.run_dir], Path(a.output)))
