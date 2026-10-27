"""Complete, versioned participant artifact identity; no evaluator secrets."""

import json
from pathlib import Path

from physicalevobench.v02.reference_artifact import ReferenceSkill, digest


def validate(payload):
    if set(payload)!={'schema','track','participant','interface','executor','task','scoring',
                       'initial_reference','skill','memory','budget_used','learning_run_id'}:
        raise ValueError('Unknown artifact fields')
    if payload['schema']!='core-artifact-1' or payload['track'] not in ('P','S'):
        raise ValueError('Unknown artifact track/version')
    if not isinstance(payload['memory'],str) or len(payload['memory'])>4000:
        raise ValueError('Bounded persistent memory required')
    if type(payload['budget_used']) is not int or not 0<=payload['budget_used']<=32:
        raise ValueError('Invalid learning budget')
    for key in ('participant','interface','executor','task','scoring','initial_reference','learning_run_id'):
        if not isinstance(payload[key],str) or not payload[key]:
            raise ValueError('Complete public artifact identity required')
    if payload['track']=='P':
        if ReferenceSkill.from_dict(payload['skill']).base_reference_sha256!=payload['initial_reference']:
            raise ValueError('Skill has different initial reference')
    else:
        from physicalevobench.core.program import Program
        Program.from_dict(payload['skill'])
    return payload


def freeze(payload,path):
    validate(payload)
    value={'payload':payload,'effective_artifact_hash':digest(payload)}
    with Path(path).open('x') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False)
    return value


def load(path):
    value=json.loads(Path(path).read_text())
    if set(value)!={'payload','effective_artifact_hash'} or digest(value['payload'])!=value['effective_artifact_hash']:
        raise ValueError('Artifact identity mismatch')
    validate(value['payload'])
    return value
