"""Preserve full real traces as modest per-seed archives, without model/runtime files."""

import argparse
import json
import shutil
import tarfile
from pathlib import Path

from physicalevobench.doctor import save_json, sha256


def package(source, destination):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    audit = json.loads((source / 'audit.json').read_text())
    if audit['status'] != 'PASS' or audit['total_physical_episodes'] != 528:
        raise ValueError('Require complete independently audited study')
    destination.mkdir(parents=True, exist_ok=False)
    for path in source.glob('*.json'):
        shutil.copyfile(path, destination / path.name)
    inventory = []
    for seed_dir in sorted(source.glob('seed-*')):
        archive = destination / (seed_dir.name + '.tar.gz')
        with tarfile.open(archive, 'w:gz', compresslevel=6) as tar:
            for path in sorted(seed_dir.rglob('*')):
                if path.is_file() and (path.suffix in {'.json', '.jsonl', '.log', '.lock'}):
                    tar.add(path, arcname=path.relative_to(source), recursive=False)
        inventory.append({'archive': archive.name, 'bytes': archive.stat().st_size,
                          'sha256': sha256(archive), 'physical_episodes': 176})
    failures = source / 'startup-failures'
    if failures.exists():
        shutil.copytree(failures, destination / failures.name)
    save_json(destination / 'archive_inventory.json', inventory)
    files = sorted(p for p in destination.rglob('*') if p.is_file())
    (destination / 'SHA256SUMS').write_text(''.join(
        f'{sha256(p)}  {p.relative_to(destination)}\n' for p in files))
    return inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--study-dir', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.study_dir, args.destination), indent=2))


if __name__ == '__main__':
    main()
