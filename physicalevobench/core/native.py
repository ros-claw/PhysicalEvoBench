"""Shared fixed IK and target envelope with participant-owned bounded programs."""

from physicalevobench.core.program import Program, ProgramFSM
from physicalevobench.v02.native import DiagnosticWorker
from physicalevobench.v02.reference_native import StateBasedReference


class ProgramReference(StateBasedReference):
    def __init__(self,worker,configuration,program):
        self.program=Program.from_dict(program)
        super().__init__(worker,configuration)

    def reset(self):
        super().reset()
        self.fsm=ProgramFSM(self.program)


class CoreWorker(DiagnosticWorker):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        import omni.usd
        from pxr import Usd, UsdGeom
        from physicalevobench.doctor import save_json
        stage=omni.usd.get_context().get_stage()
        cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_,UsdGeom.Tokens.render,UsdGeom.Tokens.proxy])
        geometry={}
        for name in ('dex_cube','table'):
            asset=self.base.scene[name]
            path=getattr(asset,'cfg',asset).prim_path.replace('{ENV_REGEX_NS}','/World/envs/env_0').replace('env_.*','env_0')
            prim=stage.GetPrimAtPath(path)
            if prim and prim.IsValid():
                box=cache.ComputeWorldBound(prim).ComputeAlignedRange()
                geometry[name]={'prim_path':path,'world_bound_min':list(box.GetMin()),
                                'world_bound_max':list(box.GetMax()),
                                'scope':'USD visual/proxy bounds; not measured support contact or collider hull'}
            else:
                geometry[name]={'status':'not_measured','path':path}
        save_json(self.output_dir/'geometry.json',geometry)

    def _snapshot(self,phase):
        result=super()._snapshot(phase)
        result['finger_position']=self.as_torch(self.robot.data.joint_pos)[0,self.finger_joint_indices].tolist()
        result['ee_position_world']=self.as_torch(self.base.scene['ee_frame'].data.target_pos_w)[:,0].tolist()
        return result

    def public_task_observation(self):
        if self.diag_cfg.get('task_version')!='core-place-public-v3-dev':
            return {}
        return {'task_goal_position':list(self.diag_cfg['public_goal']),
                'support_geometry':{'support_contact':'not_measured',
                                    'geometry_source':'see geometry.json; not inferred from reset center'}}
