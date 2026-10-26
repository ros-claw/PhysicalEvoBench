"""Content-addressed reference artifact; no chat state or arbitrary code."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True)
class ReferenceSkill:
    base_reference_sha256: str
    approach_clearance_m: float = .10
    minimum_close_s: float = .20

    def __post_init__(self):
        if not re.fullmatch('[0-9a-f]{64}',self.base_reference_sha256):
            raise ValueError('Frozen reference content hash required')
        for name,low,high in [('approach_clearance_m',.08,.12),('minimum_close_s',.2,.7)]:
            value = getattr(self,name)
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
                raise ValueError('Reference skill parameter outside public physical/time range')
            object.__setattr__(self,name,float(value))

    def to_dict(self):
        return {'schema':'reference-skill-1',**asdict(self)}

    @classmethod
    def from_dict(cls,payload):
        value=dict(payload)
        if value.pop('schema',None)!='reference-skill-1':
            raise ValueError('Unknown reference skill schema')
        return cls(**value)

    @property
    def sha256(self):
        return digest(self.to_dict())

    def configuration(self,base):
        validate(base)
        if digest(base)!=self.base_reference_sha256:
            raise ValueError('Skill refers to a different frozen reference')
        return {**base['reference_config'],'approach_clearance_m':self.approach_clearance_m,
                'minimum_close_s':self.minimum_close_s}
