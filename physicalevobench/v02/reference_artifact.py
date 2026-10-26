"""Content-addressed reference artifact; no chat state or arbitrary code."""

import hashlib
import json
import re
from pathlib import Path

from physicalevobench.v02.reference import ReferenceConfig


def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate(payload):
    if set(payload) != {'schema','source_commit','reference_config','horizon_s','task_version','checkpoint_sha256'}:
        raise ValueError('Unsupported frozen reference fields')
    if payload['schema']!='state-reference-artifact-1' or not re.fullmatch('[0-9a-f]{40}',payload['source_commit']):
        raise ValueError('Registered immutable controller source required')
    ReferenceConfig(**payload['reference_config'])
    if payload['horizon_s'] not in (5.,10.) or payload['task_version']!=f"state-reference-h{payload['horizon_s']:g}-v1":
        raise ValueError('Task version/horizon mismatch')
    if not re.fullmatch('[0-9a-f]{64}',payload['checkpoint_sha256']):
        raise ValueError('Checkpoint identity required')


def freeze(payload,path):
    validate(payload)
    with Path(path).open('x') as stream:
        json.dump({'payload':payload,'sha256':digest(payload)},stream,indent=2,sort_keys=True,allow_nan=False)
    return digest(payload)


def load(path):
    value = json.loads(Path(path).read_text())
    if set(value)!={'payload','sha256'} or digest(value['payload'])!=value['sha256']:
        raise ValueError('Frozen reference content digest mismatch')
    validate(value['payload'])
    return value['payload']
