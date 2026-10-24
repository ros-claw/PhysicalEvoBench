"""Recover published condition seeds, including the compressed negative-study evidence."""

import json
import tarfile
from pathlib import Path


def registered_seed_values(payload):
    """Include nested planned trajectories, not just completed episode job lists."""
    seeds = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {'seed', 'learner_seed', 'environment_seed'} and type(value) is int:
                # In this study's lane schema, seed=0/1/2 labels a trajectory;
                # actual RNG seeds live inside its rounds, never in this index.
                trajectory_index = (key == 'seed' and payload.get('algorithm') in ('continual', 'restart')
                                    and isinstance(payload.get('rounds'), list))
                if not trajectory_index:
                    seeds.add(value)
            elif key == 'seeds' and isinstance(value, list):
                seeds.update(v for v in value if type(v) is int)
            seeds.update(registered_seed_values(value))
    elif isinstance(payload, list):
        for value in payload:
            seeds.update(registered_seed_values(value))
    return seeds


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
                    seeds.update(registered_seed_values(payload))
    return seeds
