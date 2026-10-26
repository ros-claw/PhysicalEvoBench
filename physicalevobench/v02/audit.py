"""Recompute diagnosis from post-physics and terminal pre-reset evidence."""

import gzip
import json
import math
from pathlib import Path

from physicalevobench.stability.audit import read
from physicalevobench.v02.execution import TargetEnvelope


def records(path):
    with gzip.open(path, 'rt') as stream:
        return [json.loads(line) for line in stream]


def episode_metrics(directory, semantics):
    directory = Path(directory)
    meta = read(semantics)
    initial = read(directory/'initial_capture.json')
    terminal = read(directory/'terminal_pre_reset.json')
    controls = records(directory/'controls.jsonl.gz')
    frames = records(directory/'physics.jsonl.gz')
    if not frames or not controls or terminal['control_step'] != len(controls)-1:
        raise ValueError('Incomplete terminal/action coverage')
    if terminal['phase'] != 'terminal_pre_reset' or any(
            terminal[key] != frames[-1][key] for key in
            ('joint_position', 'joint_velocity', 'object_position', 'object_velocity', 'physics_step_global')):
        raise ValueError('Terminal state differs from final post-physics sample')
    names, limits = meta['joint_names'], meta['hard_limits']
    if meta['execution_layer'] not in ('TargetBounded', 'NumericalOnly'):
        raise ValueError('Unknown physical execution layer')
    layer = TargetEnvelope(names, limits, meta['solver_velocity_limits'], meta['control_dt'])
    layer.reset(initial['joint_position'][0])
    for i, control in enumerate(controls):
        if control['control_step'] != i:
            raise ValueError('Action sequence changed')
        if any(not math.isfinite(v) for field in ('processed_target', 'applied_target') for v in control[field]):
            raise ValueError('Nonfinite physical target')
        if meta['execution_layer'] == 'TargetBounded':
            result = layer.apply(control['processed_target'])
            if any(not math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-7)
                   for a,b in zip(result['applied_target'],control['applied_target'],strict=True)):
                raise ValueError('Physical target envelope mismatch')
            layer.previous = control['applied_target']
        elif control['processed_target'] != control['applied_target']:
            raise ValueError('Numerical-only target unexpectedly changed')
        expected = [None]*len(names)
        raw = control['accepted_raw_action'][0]
        for term_name, term in meta['action_terms'].items():
            mapping = term['mapping']
            if term_name == 'arm_action':
                targets = [v*term['scale']+offset for v,offset in zip(
                    raw[mapping['start']:mapping['stop']],term['offset'][0],strict=True)]
            else:
                targets = term['close_command'] if raw[mapping['start']] < 0 else term['open_command']
            for name,value in zip(mapping['joint_names'],targets,strict=True):
                expected[names.index(name)] = value
        if any(not math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-7)
               for a,b in zip(expected,control['processed_target'],strict=True)):
            raise ValueError('Raw action to physical target mapping mismatch')
    first, maximum, durations = None, [0.]*len(names), [0.]*len(names)
    holding_samples = {}
    previous = initial['physics_step_global']
    for frame in frames:
        stride = meta['decimation'] if meta['backend_handles_decimation'] else 1
        if (frame['phase'] != 'post_physics' or frame['physics_step_global'] != previous+stride
                or not 0 <= frame['control_step'] < len(controls)):
            raise ValueError('Physics sample ordering changed')
        dt = (frame['physics_step_global']-previous)*meta['physics_dt']
        previous = frame['physics_step_global']
        q = frame['joint_position'][0]
        if not all(math.isfinite(x) for x in (*q, *frame['joint_velocity'][0], *frame['object_position'][0], *frame['object_velocity'][0])):
            raise ValueError('Nonfinite physical state')
        depths = [max(lo-value, value-hi, 0.) for value, (lo, hi) in zip(q, limits, strict=True)]
        for j, depth in enumerate(depths):
            maximum[j] = max(maximum[j], depth)
            durations[j] += dt if depth > .001 else 0.
        if first is None and max(depths) > .001:
            first = {'control_step': frame['control_step'], 'physics_step_global': previous,
                     'time_s': (previous-initial['physics_step_global'])*meta['physics_dt'],
                     'depths': depths, 'joint_position': q,
                     'action': controls[frame['control_step']]}
        holding_samples[frame['control_step']] = frame
    if sorted(holding_samples) != list(range(len(controls))):
        raise ValueError('Control steps missing physical samples')
    per_control = 1 if meta['backend_handles_decimation'] else meta['decimation']
    if ([f['control_step'] for f in frames] !=
            [i for i in range(len(controls)) for _ in range(per_control)]):
        raise ValueError('Incomplete physical substep coverage')
    if meta['mode'] == 'FixedHorizonDiagnostic' and any(
            f['target_command'] != initial['target_command'] for f in frames):
        raise ValueError('Fixed-horizon goal changed during the episode')
    from physicalevobench.stability.metrics import holding_metrics

    samples = []
    for frame in holding_samples.values():
        samples.append({**frame, 'step_dt': meta['control_dt'],
                        'instant_predicate': math.dist(frame['object_position'][0],frame['goal_position_world'][0]) < .05})
    holding = holding_metrics(samples)
    return {'schema': 'v02-post-physics-diagnosis', 'control_steps': len(controls),
            'physics_samples': len(frames), 'terminal_pre_reset_captured': True,
            'sampling_scope': ('control-block only; hidden backend substeps NOT_MEASURED'
                               if meta['backend_handles_decimation'] else 'every exposed physics substep after scene.update'),
            'first_violation': first, 'maximum_joint_depths': maximum,
            'violation_durations_s': durations,
            'hard_boundary_terminated': bool(terminal['hard_boundary'][0]),
            'holding': holding,
            'target_limited_controls': sum(bool(c['limited_joints']) for c in controls),
            'contacts': 'ContactSensor net and cube-filtered force vectors in physics trace; no all-contact safety claim'}


def audit_run(directory):
    """Public recomputation, needs no licensed weights and performs no simulation."""
    from physicalevobench.doctor import sha256
    from physicalevobench.stability.audit import rows

    directory = Path(directory)
    reg = read(directory/'registration.json')
    if reg['schema'] != 'v02-diagnostics-1':
        raise ValueError('Unsupported v02 registration')
    if sum(p['physical_budget'] for p in reg['plans']) != reg['physical_budget']:
        raise ValueError('Registration budget mismatch')
    completed = []
    for plan in reg['plans']:
        worker = directory/plan['name']
        if read(worker/'config.json') != plan:
            raise ValueError('Worker differs from registered plan')
        if plan.get('policy_config_sha256') and sha256(worker/'policy_config.yaml') != plan['policy_config_sha256']:
            raise ValueError('Inference policy configuration digest mismatch')
        if read(worker/'process.json')['returncode'] != 0:
            raise ValueError('Native process did not complete')
        recorded = rows(worker/'episodes.jsonl')
        ledger = read(worker/'budget_ledger.json')
        if not len(recorded) == len(ledger) == len(plan['jobs']) == plan['physical_budget']:
            raise ValueError('Missing reserved physical episodes')
        meta = read(worker/'control_semantics.json')
        if any(meta[k] != plan[k] for k in ('mode', 'execution_layer')):
            raise ValueError('Execution identity mismatch')
        if any(meta[k] != reg[k] for k in ('hard_boundary', 'target_rate_caps')):
            raise ValueError('Registered execution limits changed')
        for row, job, reservation in zip(recorded, plan['jobs'], ledger, strict=True):
            episode = worker/'episodes'/job['episode_id']
            if row != read(episode/'episode.json') or row['episode_id'] != job['episode_id'] or reservation['episode_id'] != job['episode_id']:
                raise ValueError('Episode identity/reservation mismatch')
            if row['base_checkpoint_sha256'] != plan['checkpoint_sha256']:
                raise ValueError('Model lineage differs from registration')
            state = read(episode/'initial_state.json')
            if (state['condition'] != job['condition'] or
                    abs(state['mass_readback_kg'][0][0]-job['condition']['object_mass_kg']) > 1e-5):
                raise ValueError('Condition or physical mass mismatch')
            expected_id = 'PEB-Lift-v02-'+plan['mode']+'-'+plan['execution_layer']
            if row['environment_id'] != expected_id or row['schema_version'] != '0.2-diagnostic':
                raise ValueError('Versioned environment identity mismatch')
            trace_path = worker/row['trace_artifact']
            if sha256(trace_path) != row['trace_sha256']:
                raise ValueError('Legacy trace digest mismatch')
            trace = records(trace_path)
            controls = records(episode/'controls.jsonl.gz')
            if len(trace) != row['steps'] or len(controls) != row['steps']:
                raise ValueError('Action trace length mismatch')
            for i, (sample, control) in enumerate(zip(trace, controls, strict=True)):
                proposed = sample['raw_action'][0]
                accepted = [max(-1000., min(1000., v)) for v in proposed]
                if (sample['step'] != i or sample['raw_action'] != control['network_proposal']
                        or accepted != sample['applied_action'][0]
                        or sample['applied_action'] != control['accepted_raw_action']):
                    raise ValueError('Network proposal/accepted action mismatch')
            upstream = [r for r in rows(episode/'upstream.jsonl') if r.get('episode_length', 0) > 0]
            if len(upstream) != 1 or upstream[0]['episode_length'] != row['steps']:
                raise ValueError('Missing completed upstream physical episode')
            if plan['mode'] == 'LegacyInstant' and upstream[0]['success'] != row['success']:
                raise ValueError('Upstream instant outcome changed')
            if plan['mode'] == 'FixedHorizonDiagnostic' and 'reference_controller' in plan and row['success'] != row['diagnostic']['holding']['stable_success']:
                raise ValueError('Effective holding outcome changed')
            if episode_metrics(episode, worker/'control_semantics.json') != row['diagnostic']:
                raise ValueError('Post-physics diagnostic differs from raw evidence')
            completed.append({'worker': plan['name'], **row})
    if read(directory/'results.json') != {'episodes': completed, 'count': len(completed), 'learning_updates': 0}:
        raise ValueError('Registered aggregate differs from episode evidence')
    if read(directory/'status.json')['status'] != 'COMPLETED' or len(completed) != reg['physical_budget']:
        raise ValueError('Diagnostic budget was not completed')
    return {'status': 'PASS', 'phase': reg['phase'], 'episodes': len(completed),
            'scope': 'registration, reservations, model IDs, mass, upstream completions, actions, substeps and terminal recomputed; no efficacy claim'}
