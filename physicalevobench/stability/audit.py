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
    if cfg.get('action_limit') not in (None, 1000.):
        raise ValueError('Unregistered action envelope')
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
        expected_env = 'PEB-Lift-Mass-Stability-v2' if cfg.get('action_limit') else 'PEB-Lift-Mass-Stability-v1'
        if cfg.get('official_mode'):
            expected_env = 'PEB-Lift-Mass-NumericalEnvelope-v1'
        if row['environment_id'] != expected_env or row.get('action_limit') != cfg.get('action_limit'):
            raise ValueError('Environment/envelope identity mismatch')
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
            proposed = sample['raw_action'][0]
            expected_action = ([max(-1000.,min(1000.,v)) for v in proposed]
                               if cfg.get('action_limit') == 1000. else proposed)
            if sample['step'] != i or expected_action != sample['applied_action'][0] or not all(math.isfinite(v) for v in proposed + sample['applied_action'][0]):
                raise ValueError('Action integrity mismatch')
            if cfg.get('open_gripper'):
                start = read(out/'action_mapping.json')['gripper_action']['start']
                if proposed[start] != 1.:
                    raise ValueError('Known-degradation gripper command mismatch')
            if not cfg.get('official_mode'):
                goal = world_goal(sample['robot_root_position'][0], sample['robot_root_orientation'][0], sample['target_command'][0][:3])
                if math.dist(goal, sample['goal_position_world'][0]) > 1e-6:
                    raise ValueError('World-frame goal mismatch')
        if not cfg.get('official_mode'):
            metric = holding_metrics(trace)
            if metric != row['stability'] or metric != read(directory/'holding.json') or row['success'] != metric['stable_success']:
                raise ValueError('Holding score mismatch')
        upstream = [r for r in rows(directory/'upstream.jsonl') if r.get('episode_length', 0) > 0]
        if len(upstream) != 1 or upstream[0]['episode_length'] != len(trace):
            raise ValueError('Upstream evaluation completion mismatch')
        if cfg.get('official_mode'):
            if type(row['success']) is not bool or upstream[0]['success'] != row['success']:
                raise ValueError('Official success differs from stored score')
        elif upstream[0]['success'] is not False:
            raise ValueError('Training-mode evaluation success was not disabled')
        safety = summarize_safety([s['joint_position'][0] for s in trace], state['joint_limits'][0],
                                  [r['joint'] for r in row['safety']['per_joint']], .02)
        if safety != row['safety'] or safety['violation_joint_samples'] != row['joint_limit_violation_count']:
            raise ValueError('Safety score mismatch')
    save_json(out/'audit.json', {'status': 'PASS', 'physical_episodes': len(recorded),
                                'scope': ('raw trace, upstream official outcomes, numerical envelope, safety, readback, reservations'
                                          if cfg.get('official_mode') else
                                          'raw trace, pinned predicate, goal transform, holding, safety, readback, reservations')})
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
        first = []
        for row, directory in ((a, pa), (b, pb)):
            with gzip.open(Path(directory)/row['trace_artifact'], 'rt') as stream:
                first.append(json.loads(stream.readline()))
        if any(first[0][key] != first[1][key] for key in ('observation', 'joint_velocity')):
            raise ValueError('Paired initial public observation or velocity mismatch')
