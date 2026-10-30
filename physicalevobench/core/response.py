"""Measured action response and public-state command counterfactuals."""

import json
import math
from pathlib import Path

from physicalevobench.core.program import Program, ProgramFSM
from physicalevobench.development.place import starter_program
from physicalevobench.doctor import save_json
from physicalevobench.v02.audit import records


def response(directory, write=True):
    root = Path(directory)
    reg = json.loads((root/'registration.json').read_text())
    summaries = []
    for native in sorted(root.rglob('source_identity.json')):
        native = native.parent
        if not (native/'episodes.jsonl').exists():
            continue
        rows = [json.loads(s) for s in (native/'episodes.jsonl').read_text().splitlines()]
        for i, row in enumerate(rows):
            job = json.loads((native/'requests'/f'{i:03d}.json').read_text())
            if not job.get('program'):
                continue
            trace = records(native/row['trace_artifact'])
            controls = records(native/'episodes'/row['episode_id']/'controls.jsonl.gz')
            learned = ProgramFSM(Program.from_dict(job['program']))
            initial = ProgramFSM(starter_program())
            different_targets = different_gripper = different_nodes = 0
            max_target_difference = 0.
            for sample in trace:
                obs = sample['policy_diagnostics']['public']
                a, b = initial.update(obs, .02), learned.update(obs, .02)
                delta = math.dist(a['target_position'], b['target_position'])
                max_target_difference = max(max_target_difference, delta)
                different_targets += delta > 1e-6
                different_gripper += a['gripper'] != b['gripper']
                different_nodes += a.get('program_node') != b.get('program_node')
            summaries.append({'native': str(native.relative_to(root)), 'episode_id': row['episode_id'],
                               'method': job['identity'].get('method'), 'steps': row['steps'],
                               'success': row['success'], 'program_hash': Program.from_dict(job['program']).sha256,
                               'same_observation_counterfactual': {
                                   'different_target_controls': different_targets,
                                   'different_gripper_controls': different_gripper,
                                   'different_node_controls': different_nodes,
                                   'maximum_target_difference_m': max_target_difference},
                               'actually_limited_controls': sum(bool(c['limited_joints']) for c in controls),
                               'maximum_actual_joint_target_step': max((max(abs(a-b) for a, b in zip(
                                   controls[k]['applied_target'], controls[k-1]['applied_target'], strict=True))
                                   for k in range(1, len(controls))), default=0.)})
    value = {'schema': 'executable-command-response-1', 'study': reg['schema'], 'episodes': summaries,
             'scope': 'Both FSMs receive same recorded public observations; counterfactual is a command mapping, not another physical rollout. Actual targets/limits are measured separately.'}
    if write:
        save_json(root/'command_response.json', value)
    return value
