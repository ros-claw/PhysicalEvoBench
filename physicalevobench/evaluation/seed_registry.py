"""Recover published condition seeds, including the compressed negative-study evidence."""

import json
import tarfile
from pathlib import Path


def published_seeds(project_root):
    evidence = Path(project_root) / 'docs/evidence'
    seeds = {42, 1000, 1001}
    for path in evidence.rglob('initial_state.json'):
        seeds.add(json.loads(path.read_text())['condition']['seed'])
    for path in evidence.rglob('*.tar.gz'):
        with tarfile.open(path,'r:gz') as archive:
            for member in archive.getmembers():
                if '/splits/' in member.name and member.name.endswith('.jsonl') and member.isfile():
                    if member.size > 1_000_000:
                        raise ValueError('Unexpectedly large split manifest')
                    for line in archive.extractfile(member).read().decode().splitlines():
                        seeds.add(json.loads(line)['seed'])
                elif member.isfile() and member.name.rsplit('/',1)[-1] in {'config.json','registration.json'}:
                    if member.size > 1_000_000:
                        raise ValueError('Unexpectedly large configuration')
                    payload=json.loads(archive.extractfile(member).read())
                    conditions=payload.get('conditions',[])
                    if isinstance(conditions,list):
                        seeds.update(c['seed'] for c in conditions)
                    seeds.update(j['condition']['seed'] for j in payload.get('jobs', []))
                    if 'environment_seed' in payload:
                        seeds.add(payload['environment_seed'])
    return seeds
