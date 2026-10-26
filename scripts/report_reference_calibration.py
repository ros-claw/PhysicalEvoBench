"""Recompute reference transitions and development/confirmation gates."""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read
from physicalevobench.v02.audit import audit_run, records
from physicalevobench.v02.reference import BoundedJointIntegral, ReferenceConfig, ReferenceFSM
from physicalevobench.v02.reference_artifact import digest


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
        initial = read(ep/'initial_capture.json')
        config = ReferenceConfig(**cfg['reference_config'])
        fsm = ReferenceFSM(config)
        integral = BoundedJointIntegral(config.joint_integral_gain_s,config.joint_integral_limit_rad)
        phases,transitions = Counter(),[]
        errors = []
        for sample in trace:
            diagnostic = sample['policy_diagnostics']
            public = diagnostic['public']
            decision = fsm.update(public,meta['control_dt'])
            if decision != diagnostic['decision']:
                raise ValueError('Reference phase or state guard differs from raw observations')
            if config.joint_integral_gain_s>0:
                expected_bias=integral.update(diagnostic['joint_error_feedback_rad'],meta['control_dt'],decision['phase'] in ('lift','hold'))
                if expected_bias!=diagnostic['bounded_joint_integral_rad']:
                    raise ValueError('Reference bounded integral differs from observable feedback')
            if (public['ee_position'] != sample['ee_position'][0][0] or
                    public['object_position'] != sample['object_position'][0] or
                    public['object_velocity'] != sample['object_velocity'][0][:3] or
                    public['goal_position'] != sample['goal_position_world'][0]):
                raise ValueError('Reference public geometry differs from trace')
            fingers = [i for i,n in enumerate(meta['joint_names']) if 'finger' in n]
            if public['finger_position'] != [sample['joint_position'][0][i] for i in fingers]:
                raise ValueError('Reference finger aperture differs from physical trace')
            previous_frame = initial if sample['step']==0 else frames[sample['step']*meta['decimation']-1]
            def force_magnitude(value):
                if isinstance(value[0],list):
                    return max(force_magnitude(v) for v in value)
                return math.sqrt(sum(v*v for v in value))

            contacts = [force_magnitude(previous_frame['contacts'][side]['cube_force_matrix_w']['value'])
                        for side in ('left','right')]
            if any(not math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-4) for a,b in zip(contacts,public['cube_contact_force'],strict=True)):
                raise ValueError('Reference contact guard differs from preceding physics sample')
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
        reference_safe = not any(e['any_violation'] or e['hard_event'] for e in reference)
        result['reference_gate_passed'] = positive and reference_safe and len(negative)==12 and not any(e['holding'] for e in negative)
        result['scope'] = 'Independent finite reference calibration only; no autonomous or stable self-evolution claim'
    save_json(directory/'reference_diagnosis.json',result)
    return result


def terminal_followup(directory):
    """Separate additive evidence; does not change frozen success definitions."""
    directory=Path(directory)
    audit_run(directory)
    result=[]
    for row in read(directory/'results.json')['episodes']:
        worker=directory/row['worker']
        meta=read(worker/'control_semantics.json')
        episode=worker/'episodes'/row['episode_id']
        frames=records(episode/'physics.jsonl.gz')
        controls={frame['control_step']:frame for frame in frames}
        span=0
        first_hold=None
        left_after_hold=False
        for step,frame in controls.items():
            distance=math.dist(frame['object_position'][0],frame['goal_position_world'][0])
            speed=math.sqrt(sum(v*v for v in frame['object_velocity'][0][:3]))
            qualifies=distance<.05 and speed<=.2
            span=span+1 if qualifies else 0
            if first_hold is None and (span-1)*meta['control_dt']>=.3-1e-12:
                first_hold=(step+1)*meta['control_dt']
            if first_hold is not None and distance>=.05:
                left_after_hold=True
        last=frames[-1]
        distance=math.dist(last['object_position'][0],last['goal_position_world'][0])
        speed=math.sqrt(sum(v*v for v in last['object_velocity'][0][:3]))
        result.append({'worker':row['worker'],'episode_id':row['episode_id'],
                       'first_effective_hold_time_s':first_hold,'left_goal_after_first_hold':left_after_hold,
                       'terminal_goal_distance_m':distance,'terminal_speed_m_s':speed,
                       'terminal_effective_predicate':distance<.05 and speed<=.2})
    value={'schema':'reference-terminal-followup-1','episodes':result,
           'scope':'Control-sampled post-physics followup and terminal pre-reset; additive observation, no changed gate'}
    save_json(directory/'reference_terminal_followup.json',value)
    return value


def controller_identities(directory):
    """Full program identity; preserve inherited legacy checkpoint-skill fields."""
    directory=Path(directory)
    reg=read(directory/'registration.json')
    entries=[]
    for plan in reg['plans']:
        content={'source_commit':reg['source_commit'],**{key:plan[key] for key in
                 ('reference_controller','reference_config','task_version','horizon_s','execution_layer','checkpoint_sha256')}}
        entries.append({'worker':plan['name'],'effective_controller_sha256':digest(content),'content':content,
                        'legacy_row_skill_sha256':read(directory/plan['name']/'episodes'/plan['jobs'][0]['episode_id']/'episode.json')['skill_sha256']})
    value={'schema':'reference-controller-identities-1','controllers':entries,
           'scope':'Identity includes executable source/controller/config/task, never conditions or results. Legacy row skill_sha256 is inherited checkpoint/gain context, not full reference identity.'}
    save_json(directory/'controller_identity.json',value)
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    a=p.parse_args()
    print(json.dumps(report(a.run_dir),indent=2))
