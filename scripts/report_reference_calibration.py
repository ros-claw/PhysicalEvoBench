"""Recompute reference transitions and development/confirmation gates."""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read
from physicalevobench.v02.audit import audit_run, records
from physicalevobench.v02.reference import ReferenceConfig, ReferenceFSM


def report(directory):
    directory = Path(directory)
    audit = audit_run(directory)
    reg = read(directory/'registration.json')
    episodes = []
    for row in read(directory/'results.json')['episodes']:
        worker = directory/row['worker']
        cfg,meta = read(worker/'config.json'),read(worker/'control_semantics.json')
        ep = worker/'episodes'/row['episode_id']
        trace,frames = records(ep/'trace.jsonl.gz'),records(ep/'physics.jsonl.gz')
        fsm = ReferenceFSM(ReferenceConfig(**cfg['reference_config']))
        phases,transitions = Counter(),[]
        errors = []
        for sample in trace:
            diagnostic = sample['policy_diagnostics']
            public = diagnostic['public']
            decision = fsm.update(public,meta['control_dt'])
            if decision != diagnostic['decision']:
                raise ValueError('Reference phase or state guard differs from raw observations')
            if (public['ee_position'] != sample['ee_position'][0][0] or
                    public['object_position'] != sample['object_position'][0] or
                    public['object_velocity'] != sample['object_velocity'][0][:3] or
                    public['goal_position'] != sample['goal_position_world'][0]):
                raise ValueError('Reference public geometry differs from trace')
            q = public['ee_quaternion_xyzw']
            angle = 2*math.acos(min(1.,abs(q[0])/math.sqrt(sum(v*v for v in q))))
            if not math.isclose(angle,public['orientation_error'],abs_tol=1e-3):
                raise ValueError('Reference orientation guard mismatch')
            gripper = sample['raw_action'][0][meta['action_terms']['gripper_action']['mapping']['start']]
            expected = 1 if cfg['reference_controller']=='StateBasedReferenceOpen' or decision['gripper']=='open' else -1
            if gripper != expected:
                raise ValueError('Reference gripper command differs from phase')
            phases[decision['phase']] += 1
            errors.append(decision['position_error_m'])
            if decision['transition_reason']:
                transitions.append({'control_step':sample['step'],**decision})
        metric = row['diagnostic']
        state = read(ep/'initial_state.json')['condition']
        violated = metric['first_violation'] is not None
        depth = max(d for n,d in zip(meta['joint_names'],metric['maximum_joint_depths'],strict=True) if 'finger' in n)
        episodes.append({'worker':row['worker'],'episode_id':row['episode_id'],'condition_id':row['condition_id'],
                         'mass_kg':state['object_mass_kg'],'steps':row['steps'],'termination':row['termination_reason'],
                         'instant':metric['holding']['instant_success'],'holding':metric['holding']['stable_success'],
                         'holding_span_s':metric['holding']['maximum_holding_span_s'],
                         'any_violation':violated,'hard_event':metric['hard_boundary_terminated'],
                         'maximum_finger_depth_m':depth,'phase_control_steps':dict(phases),
                         'last_phase':trace[-1]['policy_diagnostics']['phase'],
                         'first_position_error_m':errors[0],'last_position_error_m':errors[-1],
                         'transitions':transitions,'physics_samples':len(frames)})
    grouped = defaultdict(list)
    for e in episodes:
        grouped[(e['worker'],e['mass_kg'])].append(e)
    surface = {f'{worker}-{mass:g}kg':{'episodes':len(group),'instant':sum(e['instant'] for e in group),
               'holding':sum(e['holding'] for e in group),'violating_episodes':sum(e['any_violation'] for e in group),
               'maximum_holding_span_s':max(e['holding_span_s'] for e in group),
               'maximum_finger_depth_m':max(e['maximum_finger_depth_m'] for e in group)}
               for (worker,mass),group in sorted(grouped.items())}
    safe = not any(e['any_violation'] or e['hard_event'] for e in episodes)
    result = {'schema':'state-reference-report-1','registration_sha256':sha256(directory/'registration.json'),
              'audit':audit,'task_version':reg['plans'][0]['task_version'],'episodes':episodes,'surface':surface,
              'new_training_transitions':0,'Agent_comparison':'NOT_RUN'}
    if reg['phase']=='reference-development':
        result['qualified_for_confirmation'] = len(episodes)==4 and sum(e['holding'] for e in episodes)>=3 and safe
        result['time_extension_evidence'] = any(e['termination']=='horizon' and e['last_phase'] in ('approach','descend','close','probe')
                                               and e['first_position_error_m']-e['last_position_error_m']>.05
                                               for e in episodes)
    else:
        reference = [e for e in episodes if e['worker']=='StateBasedReference']
        negative = [e for e in episodes if e['worker']=='StateBasedReferenceOpen']
        positive = len(reference)==12 and all(sum(e['holding'] for e in reference if e['mass_kg']==m)>=5 for m in (.1,.4))
        result['reference_gate_passed'] = positive and safe and len(negative)==12 and not any(e['holding'] for e in negative)
        result['scope'] = 'Independent finite reference calibration only; no autonomous or stable self-evolution claim'
    save_json(directory/'reference_diagnosis.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    a=p.parse_args()
    print(json.dumps(report(a.run_dir),indent=2))
