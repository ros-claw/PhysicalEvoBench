"""Method-neutral, fixed pre-agent support probe, then restore the registered state."""

import gzip
import json
import math
import statistics

from physicalevobench.adapters.lift_worker import tensor_json
from physicalevobench.core.errors import InitializationInvalid
from physicalevobench.core.scene_diagnostics import HoldReference,state
from physicalevobench.doctor import save_json

STEPS=200


def flatten(x):
    if isinstance(x,list):
        return [v for y in x for v in flatten(y)]
    return [x]


def support(worker):
    sensor=worker.base.scene['esl_support']
    result={'field_units':'newtons, world axes; raw pair impulse in N*s',
            'filter':'Cube net normal sensor + actual PhysX ContactReport actor/collider pair',
            'cube_table_normal_force_matrix_w':'not_measured; static table is not a tensor rigid-body filter'}
    try:
        result['cube_net_normal_force_w']=tensor_json(worker.as_torch(sensor.data.net_normal_forces_w))
    except (AttributeError,RuntimeError,TypeError) as error:
        result['cube_net_normal_force_w']='not_measured'
        result['reason']=str(error)[:120]
    try:
        from omni.physx import get_physx_simulation_interface
        from pxr import PhysicsSchemaTools
        report=get_physx_simulation_interface().get_contact_report()
        headers,data=report[:2]
        pairs=[]
        for header in headers:
            paths={key:str(PhysicsSchemaTools.intToSdfPath(getattr(header,key)))
                   for key in ('actor0','actor1','collider0','collider1')}
            if not any('/dex_cube' in p for p in paths.values()) or not any('/table' in p for p in paths.values()):
                continue
            contacts=[]
            for i in range(header.contact_data_offset,header.contact_data_offset+header.num_contact_data):
                item=data[i]
                impulse=list(item.impulse)
                normal=list(item.normal)
                contacts.append({'impulse_Ns':impulse,'normal_world':normal,
                    'normal_force_N':abs(sum(a*b for a,b in zip(impulse,normal,strict=True)))/worker.base.physics_dt,
                    'position_world':list(item.position)})
            pairs.append({**paths,'event_type':str(header.type),'contacts':contacts})
        result['cube_table_contact_reports']=pairs
    except (AttributeError,RuntimeError,TypeError,ValueError) as error:
        result['cube_table_contact_reports']='not_measured'
        result['pair_report_reason']=str(error)[:160]
    result['physics_step']=worker.base._sim_step_counter
    return result


def raycasts(worker):
    import carb
    from omni.physx import get_physx_scene_query_interface

    hits=[]
    def callback(hit):
        def value(key):
            return hit.get(key) if isinstance(hit,dict) else getattr(hit,key,None)
        hits.append({'collision':str(value('collision')),'rigid_body':str(value('rigid_body')),
                     'position':list(value('position')) if value('position') is not None else None,
                     'normal':list(value('normal')) if value('normal') is not None else None,
                     'distance':value('distance')})
        return True
    try:
        query=get_physx_scene_query_interface()
        for x,y in [(.5,0.),(.6,0.),(.5,.1)]:
            query.raycast_all(carb.Float3(x,y,.5),carb.Float3(0.,0.,-1.),2.,callback)
        return {'status':'MEASURED','hits':hits,
                'table_shape_hit':any('/table' in h['collision'] for h in hits),
                'scope':'Runtime PhysX scene query, not USD visual bounds or full cooked mesh data'}
    except (AttributeError,RuntimeError,TypeError) as error:
        return {'status':'not_measured','reason':str(error)[:200],'table_shape_hit':False}


def decision(frames,mass,shape_hit):
    tail=frames[-40:]
    if len(tail)!=40 or not shape_hit:
        return False,'runtime_table_shape_or_sample_coverage_missing'
    heights=[f['object_position'][0][2] for f in tail]
    velocities=[math.sqrt(sum(v*v for v in f['object_velocity'][0][:3])) for f in tail]
    forces=[]
    for f in tail:
        force=f['support']['cube_net_normal_force_w']
        if not isinstance(force,list):
            return False,'necessary_support_sensor_unavailable'
        forces.append(math.sqrt(sum(v*v for v in flatten(force))))
    values=heights+velocities+forces+[x for f in tail for k in ('joint_position','joint_velocity','object_position','object_velocity','object_orientation','mass','inertia') for x in flatten(f[k])]
    if not all(math.isfinite(v) for v in values):
        return False,'nonfinite_pre_agent_state'
    # Legal support/initial-motion checks only; no task score or candidate inspected.
    if not all(.005<=z<=.08 for z in heights):
        return False,'cube_not_on_registered_support_region'
    if max(velocities)>.02 or statistics.median(forces)<.5*mass*9.81:
        return False,'support_or_motion_not_stable'
    return True,'fixed_support_probe_passed'


def prepare(worker):
    import torch

    base=worker.base
    cube=base.scene['dex_cube']
    q=worker.as_torch(worker.robot.data.joint_pos).clone()
    qd=worker.as_torch(worker.robot.data.joint_vel).clone()
    root=worker.as_torch(cube.data.root_state_w).clone()
    mass=float(worker.as_torch(cube.data.body_mass).reshape(-1)[0])
    initial=state(worker)
    model2=worker.diag_cfg.get('initialization_profile')=='support-probe-restore-2'
    if model2:
        from physicalevobench.core.parameter_transport import read,validate
        model_before=read(worker)
        model_valid,model_reason=validate(initial,model_before,worker.current_condition['object_mass_kg'])
    body_view=cube.root_view
    shape_readback={'body_count':body_view.count,'maximum_shapes':body_view.max_shapes}
    worker.recording=False
    hold=HoldReference(worker)
    hold.reset()
    action=hold.get_action(worker.env,None)
    base.action_manager.process_action(action)
    frames=[]
    shapes_before=raycasts(worker)
    for i in range(STEPS):
        base.action_manager.apply_action()
        base.scene.write_data_to_sim()
        base._sim_step_counter+=1
        base.sim.step(render=False)
        base.scene.update(dt=base.physics_dt)
        frames.append({'probe_step':i,'time_s':(i+1)*base.physics_dt,**state(worker),
                       'support':support(worker)})
    shapes_after=raycasts(worker)
    valid,reason=decision(frames,mass,shapes_after['table_shape_hit'])
    if shape_readback['body_count']!=1 or shape_readback['maximum_shapes']<1:
        valid,reason=False,'necessary_body_shape_missing'
    requested=worker.current_condition['object_mass_kg']
    if not math.isfinite(mass) or abs(mass-requested)>1e-6:
        valid,reason=False,'physical_parameter_readback_mismatch'
    if model2:
        model_after=read(worker)
        valid_after,reason_after=validate(frames[-1],model_after,requested)
        if not model_valid or not valid_after:
            valid,reason=False,model_reason if not model_valid else reason_after
    directory=worker.ready_directory
    with gzip.open(directory/'readiness_probe.jsonl.gz','wt') as f:
        for row in frames:
            f.write(json.dumps(row,allow_nan=False)+'\n')
    receipt={'schema':'esl-episode-ready-1','profile':worker.diag_cfg['initialization_profile'],
             'status':'READY' if valid else 'INIT_INVALID','reason':reason,
             'physical_substeps':STEPS,'physical_seconds':STEPS*base.physics_dt,
             'task_clock_started':False,'probe_control':'fixed original joint targets/open gripper; no participant action',
             'body_shape_readback':shape_readback,'requested_mass_kg':requested,'mass_readback_kg':mass,'pre_probe':initial,
             'post_probe':frames[-1],'runtime_shapes_before':shapes_before,
             'runtime_shapes_after':shapes_after,'retries':0,
             'distribution':'Probe uses the registered condition; restore its original joint/root states without changing mass/inertia or rerandomizing; solver/contact history is warmed and therefore a new execution version.'}
    if model2:
        receipt.update(physx_model_before_probe=model_before,physx_model_after_probe=model_after,
                       parameter_handoff='Cube PhysX setters fenced after GPU-to-pinned-CPU copy, before CPU input consumption')
    if valid:
        worker.robot.write_joint_state_to_sim(q,qd)
        cube.write_root_state_to_sim(root)
        worker.robot.set_joint_position_target(q)
        base.scene.write_data_to_sim()
        base.sim.forward()
        base.scene.update(dt=0.)
        restored=state(worker)
        receipt['restored']=restored
        for key in ('joint_position','joint_velocity','object_position','object_velocity','object_orientation','mass','inertia'):
            if any(abs(a-b)>1e-6 for a,b in zip(flatten(initial[key]),flatten(restored[key]),strict=True)):
                valid,reason=False,'registered_state_restore_mismatch:'+key
                break
        if model2:
            receipt['physx_model_at_task_start']=read(worker)
            checked,why=validate(restored,receipt['physx_model_at_task_start'],requested)
            if not checked:
                valid,reason=False,why
        receipt['runtime_shapes_at_task_start']=raycasts(worker)
        if not receipt['runtime_shapes_at_task_start']['table_shape_hit']:
            valid,reason=False,'table_shape_missing_after_restore'
    receipt.update(status='READY' if valid else 'INIT_INVALID',reason=reason)
    save_json(directory/'readiness.json',receipt)
    if not valid:
        raise InitializationInvalid(reason)
    worker.layer.reset(worker.as_torch(worker.robot.data.joint_pos)[0].tolist())
    worker.initial_capture=worker._snapshot('initial_post_ready_restored')
    worker.recording=True
    # No participant action, graph, score, seed selection or model call is used by this phase.
    assert torch.isfinite(worker.as_torch(cube.data.root_pos_w)).all()
