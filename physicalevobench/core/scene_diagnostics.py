"""Evaluator-only initialization observations; no participant observations added."""

import time

from physicalevobench.adapters.lift_worker import tensor_json


class HoldReference:
    """Fixed initial joint targets, open fingers, no approach or grasp."""

    def __init__(self, worker):
        self.worker=worker
        self.diagnostics=None

    def reset(self):
        w=self.worker
        self.q=w.as_torch(w.robot.data.joint_pos).clone()

    def get_action(self,env,obs):
        import torch

        w=self.worker
        term=w.base.action_manager.get_term('arm_action')
        action=torch.zeros((1,8),device=w.base.device)
        action[:,w.arm_slice]=(self.q[:,w.joint_indices['arm_action']]-term._offset)/term._scale
        action[:,w.action_mapping['gripper_action']['start']]=1.
        self.diagnostics={'diagnostic_control':'fixed_initial_joint_target_open_gripper',
                          'support_contact':'not_measured'}
        return action


def state(worker):
    cube=worker.base.scene['dex_cube']
    return {'object_position':tensor_json(worker.as_torch(cube.data.root_pos_w)),
            'object_velocity':tensor_json(worker.as_torch(cube.data.root_vel_w)),
            'joint_position':tensor_json(worker.as_torch(worker.robot.data.joint_pos)),
            'mass':tensor_json(worker.as_torch(cube.data.body_mass)),
            'inertia':tensor_json(worker.as_torch(cube.data.body_inertia)),
            'physics_step':worker.base._sim_step_counter}


def describe(worker):
    import omni.usd
    from pxr import Usd,UsdGeom,UsdPhysics

    stage=omni.usd.get_context().get_stage()
    result={'support_contact':'not_measured','cooked_collider':'not_measured',
            'construction_before_instrumentation':'not_measured','assets':{}}
    for name in ('dex_cube','table'):
        asset=worker.base.scene[name]
        path=worker.base.scene.env_prim_paths[0]+'/'+getattr(asset,'cfg',asset).prim_path.rsplit('/',1)[-1]
        root=stage.GetPrimAtPath(path)
        bodies=[]
        for prim in Usd.PrimRange(root):
            if prim.HasAPI(UsdPhysics.CollisionAPI) or prim.HasAPI(UsdPhysics.RigidBodyAPI):
                bodies.append({'path':str(prim.GetPath()),'type':prim.GetTypeName(),
                    'schemas':list(prim.GetAppliedSchemas()),
                    'collision_enabled':UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() if prim.HasAPI(UsdPhysics.CollisionAPI) else None,
                    'attributes':{a.GetName():str(a.Get()) for a in prim.GetAttributes() if any(k in a.GetName().lower() for k in ('physics:','physx','xform'))},
                    'relationships':{r.GetName():[str(p) for p in r.GetTargets()] for r in prim.GetRelationships()},
                    'world_transform':str(UsdGeom.XformCache().GetLocalToWorldTransform(prim))})
        view={}
        try:
            v=asset.root_view
            view['class']=str(type(v))
            for key in ('count','max_shapes','prim_paths','body_names','num_bodies'):
                try:
                    x=getattr(v,key)
                    view[key]=x if isinstance(x,(int,str,list,bool)) else str(x)
                except (AttributeError,RuntimeError,TypeError):
                    view[key]='not_measured'
        except (AttributeError,RuntimeError):
            view={'status':'not_measured'}
        result['assets'][name]={'prim_path':path,'USD_bodies_and_colliders':bodies,'runtime_view':view}
    try:
        result['assets_loading']=bool(worker.base.sim.physics_manager.assets_loading())
    except (AttributeError,RuntimeError):
        result['assets_loading']='not_measured'
    return result


def install(worker):
    from physicalevobench.doctor import save_json

    worker.initialization_events=[]
    def record(name):
        worker.initialization_events.append({'event':name,'monotonic_s':time.monotonic(),**state(worker)})
    # Preserve the current reset/forward path. This first diagnostic does not add settling.
    for owner,name in [(worker.base,'_reset_idx'),(worker.base.sim,'forward'),
                       (worker.base.scene['dex_cube'],'set_masses_index'),
                       (worker.base.scene['dex_cube'],'set_inertias_index')]:
        original=getattr(owner,name,None)
        if original is None:
            record(name+':not_measured')
            continue
        def wrapped(*args,_f=original,_name=name,**kwargs):
            record(_name+':before')
            value=_f(*args,**kwargs)
            record(_name+':after')
            return value
        setattr(owner,name,wrapped)
    reset=worker.env.reset
    def observed_reset(*args,**kwargs):
        record('explicit_reset:before')
        value=reset(*args,**kwargs)
        record('explicit_reset:after')
        save_json(worker.output_dir/'initialization_runtime.json',describe(worker))
        return value
    worker.env.reset=observed_reset
    update=worker.base.scene.update
    def observed_update(dt):
        value=update(dt)
        if worker.recording:
            record('scene_update:after')
        return value
    worker.base.scene.update=observed_update
    record('instrumentation_installed_after_construction')
