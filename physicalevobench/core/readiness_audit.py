"""Recompute the pre-agent boundary from recorded probe states, without physics."""

import json
import math
from pathlib import Path

from physicalevobench.core.readiness import STEPS,decision,flatten
from physicalevobench.v02.audit import records


def audit_readiness(directory,condition,row):
    directory=Path(directory)
    r=json.loads((directory/'readiness.json').read_text())
    frames=records(directory/'readiness_probe.jsonl.gz')
    if (r['profile']!='support-probe-restore-1' or len(frames)!=STEPS or
            r['physical_substeps']!=STEPS or r['task_clock_started'] is not False or r['retries']!=0 or
            any(f['probe_step']!=i or not math.isclose(f['time_s'],(i+1)*.005,abs_tol=1e-12)
                for i,f in enumerate(frames)) or r['post_probe']!=frames[-1]):
        raise ValueError('Pre-agent probe coverage or timing changed')
    for name in ('runtime_shapes_before','runtime_shapes_after','runtime_shapes_at_task_start'):
        if name in r and r[name].get('status')=='MEASURED':
            measured=any('/table' in h['collision'] for h in r[name]['hits'])
            if r[name]['table_shape_hit']!=measured:
                raise ValueError('Runtime table shape flag differs from raw ray hits')
    if any(frames[i]['support']['physics_step']!=frames[0]['support']['physics_step']+i for i in range(STEPS)):
        raise ValueError('Support sensor timestamps are not consecutive physics steps')
    mass=r['mass_readback_kg']
    if any(abs(v-mass)>1e-6 for f in frames for v in flatten(f['mass'])):
        raise ValueError('Probe physical mass differs from readback')
    valid,reason=decision(frames,mass,r['runtime_shapes_after']['table_shape_hit'])
    shape=r['body_shape_readback']
    if shape['body_count']!=1 or shape['maximum_shapes']<1:
        valid,reason=False,'necessary_body_shape_missing'
    requested=condition['object_mass_kg']
    if r['requested_mass_kg']!=requested or not math.isfinite(mass) or abs(mass-requested)>1e-6:
        valid,reason=False,'physical_parameter_readback_mismatch'
    if valid:
        initial,restored=r['pre_probe'],r.get('restored',{})
        for key in ('joint_position','joint_velocity','object_position','object_velocity','object_orientation','mass','inertia'):
            if key not in restored or any(abs(a-b)>1e-6 for a,b in zip(flatten(initial[key]),flatten(restored[key]),strict=True)):
                valid,reason=False,'registered_state_restore_mismatch:'+key
                break
        if not r.get('runtime_shapes_at_task_start',{}).get('table_shape_hit'):
            valid,reason=False,'table_shape_missing_after_restore'
    if r['status']!=('READY' if valid else 'INIT_INVALID') or r['reason']!=reason:
        raise ValueError('Pre-agent validity differs from raw probe')
    if not valid and (row['success'] is not None or row['steps']!=0 or row['execution_status']!='INIT_INVALID'):
        raise ValueError('Invalid initialization became a participant outcome')
    if valid and row['execution_status']=='INIT_INVALID':
        raise ValueError('Valid initialization incorrectly excluded')
    return {'status':r['status'],'physics_substeps':STEPS,'physics_seconds':r['physical_seconds']}
