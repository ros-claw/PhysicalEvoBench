"""Actual recorded controller traces remain replayable; perturbed actions are rejected."""

import json
import tarfile
from pathlib import Path

import pytest

from physicalevobench.evaluation.temporal_audit import audit_temporal_episode


@pytest.mark.parametrize('group,trial',[('group-0','hold10'),('group-1','smooth50')])
def test_actual_temporal_trace_and_tampering(tmp_path,group,trial):
    repo=Path(__file__).resolve().parents[1]
    archive=repo/'docs/evidence/temporal-development-20261022-001/exploration.tar.gz'
    prefix=f'exploration/{group}/'
    with tarfile.open(archive,'r:gz') as tar:
        candidates=[m for m in tar.getmembers() if m.name.startswith(prefix+f'episodes/{trial}-')
                    and m.name.endswith('/episode.json')]
        selected=sorted(candidates,key=lambda m:m.name)[0]
        row=json.load(tar.extractfile(selected))
        relative=Path(row['trace_artifact']).parent
        dest=tmp_path/relative
        dest.mkdir(parents=True)
        for name in ['episode.json','initial_state.json','skill.json','trace.jsonl','upstream.jsonl']:
            (dest/name).write_bytes(tar.extractfile(prefix+str(relative/name)).read())
        mapping=json.load(tar.extractfile(prefix+'action_mapping.json'))
    condition=json.loads((dest/'initial_state.json').read_text())['condition']
    audit_temporal_episode(tmp_path,row,condition,mapping)
    path=dest/'trace.jsonl'
    trace=[json.loads(line) for line in path.read_text().splitlines()]
    if trial=='hold10':
        index=mapping['gripper_action']['start']
        step=next(s for s in trace if s['applied_action'][0][index]!=s['raw_action'][0][index])
        step['applied_action'][0][index]=1.
    else:
        trace[1]['applied_action'][0][mapping['arm_action']['start']]+=.1
    path.write_text(''.join(json.dumps(s)+'\n' for s in trace))
    with pytest.raises(ValueError,match='temporal action'):
        audit_temporal_episode(tmp_path,row,condition,mapping)
