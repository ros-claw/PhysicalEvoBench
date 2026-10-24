"""Recompute holding, actions, physical readbacks and safety from raw traces."""

import gzip
import json
import math
from pathlib import Path

from physicalevobench.calibration.safety import summarize_safety
from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.metrics import holding_metrics


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def world_goal(position, quaternion, local):
    x, y, z, w = quaternion  # Pinned Isaac Lab 17 uses xyzw, including root state.
    ux, uy, uz = local
    # Independent scalar quaternion-vector rotation (upstream uses torch helpers).
    tx, ty, tz = 2*(y*uz-z*uy), 2*(z*ux-x*uz), 2*(x*uy-y*ux)
    return [position[0]+ux+w*tx+y*tz-z*ty,
            position[1]+uy+w*ty+z*tx-x*tz,
            position[2]+uz+w*tz+x*ty-y*tx]


def audit_worker(out):
    out = Path(out)
    cfg, recorded = read(out/'config.json'), rows(out/'episodes.jsonl')
    jobs = cfg['jobs']
    ledger = read(out/'budget_ledger.json')
    if len(recorded) != len(jobs) or len(ledger) != len(jobs) or len(jobs) > cfg['physical_budget']:
        raise ValueError('Incomplete physical budget')
    if read(out/'process.json')['returncode'] != 0:
        raise ValueError('Native process failed')
    for row, job, reservation in zip(recorded, jobs, ledger, strict=True):
        directory = out/'episodes'/row['episode_id']
        if row != read(directory/'episode.json') or row['episode_id'] != job['episode_id'] or reservation['episode_id'] != job['episode_id']:
            raise ValueError('Episode index or reservation mismatch')
        if row['base_checkpoint_sha256'] != cfg['checkpoint_sha256']:
            raise ValueError('Model lineage mismatch')
        state = read(directory/'initial_state.json')
        if state['condition'] != job['condition'] or abs(state['mass_readback_kg'][0][0]-job['condition']['object_mass_kg']) > 1e-5:
            raise ValueError('Physical mass/condition mismatch')
        trace_path = out/row['trace_artifact']
        if sha256(trace_path) != row['trace_sha256']:
            raise ValueError('Trace digest mismatch')
        with gzip.open(trace_path, 'rt') as stream:
            trace = [json.loads(line) for line in stream]
        if len(trace) != row['steps'] or not trace:
            raise ValueError('Trace length mismatch')
        for i, sample in enumerate(trace):
            if sample['step'] != i or sample['raw_action'] != sample['applied_action'] or not all(math.isfinite(v) for v in sample['applied_action'][0]):
                raise ValueError('Action integrity mismatch')
            goal = world_goal(sample['robot_root_position'][0], sample['robot_root_orientation'][0], sample['target_command'][0][:3])
            if math.dist(goal, sample['goal_position_world'][0]) > 1e-6:
                raise ValueError('World-frame goal mismatch')
        metric = holding_metrics(trace)
        if metric != row['stability'] or metric != read(directory/'holding.json') or row['success'] != metric['stable_success']:
            raise ValueError('Holding score mismatch')
        upstream = [r for r in rows(directory/'upstream.jsonl') if r.get('episode_length', 0) > 0]
        if len(upstream) != 1 or upstream[0]['episode_length'] != len(trace) or upstream[0]['success'] is not False:
            raise ValueError('Training-mode evaluation completion mismatch')
        safety = summarize_safety([s['joint_position'][0] for s in trace], state['joint_limits'][0],
                                  [r['joint'] for r in row['safety']['per_joint']], trace[0]['step_dt'])
        if safety != row['safety'] or safety['violation_joint_samples'] != row['joint_limit_violation_count']:
            raise ValueError('Safety score mismatch')
    save_json(out/'audit.json', {'status': 'PASS', 'physical_episodes': len(recorded),
                                'scope': 'raw trace, pinned predicate, goal transform, safety, readback, reservations'})
    return recorded


def assert_pairs(left, right):
    if len(left) != len(right):
        raise ValueError('Paired sample size mismatch')
    for (a, pa), (b, pb) in zip(left, right, strict=True):
        if a['condition_id'] != b['condition_id']:
            raise ValueError('Paired condition mismatch')
        sa = read(Path(pa)/a['initial_state_artifact'])
        sb = read(Path(pb)/b['initial_state_artifact'])
        if sa != sb:
            raise ValueError('Paired initial physical state mismatch')
