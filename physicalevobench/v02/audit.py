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
    if terminal['joint_position'] != frames[-1]['joint_position'] or terminal['object_position'] != frames[-1]['object_position']:
        raise ValueError('Terminal state differs from final post-physics sample')
    names, limits = meta['joint_names'], meta['hard_limits']
    layer = TargetEnvelope(names, limits, meta['solver_velocity_limits'], meta['control_dt'])
    layer.reset(initial['joint_position'][0])
    for i, control in enumerate(controls):
        if control['control_step'] != i:
            raise ValueError('Action sequence changed')
        if meta['execution_layer'] == 'TargetBounded':
            result = layer.apply(control['processed_target'])
            if any(not math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-7)
                   for a,b in zip(result['applied_target'],control['applied_target'],strict=True)):
                raise ValueError('Physical target envelope mismatch')
            layer.previous = control['applied_target']
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
        if frame['phase'] != 'post_physics' or frame['physics_step_global'] <= previous:
            raise ValueError('Physics sample ordering changed')
        dt = (frame['physics_step_global']-previous)*meta['physics_dt']
        previous = frame['physics_step_global']
        q = frame['joint_position'][0]
        if not all(math.isfinite(x) for x in (*q, *frame['object_position'][0], *frame['object_velocity'][0])):
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
