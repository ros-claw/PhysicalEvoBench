"""Shared fixed IK and target envelope with participant-owned bounded programs."""

from physicalevobench.core.program import Program, ProgramFSM
from physicalevobench.v02.native import DiagnosticWorker
from physicalevobench.v02.reference_native import StateBasedReference


class ProgramReference(StateBasedReference):
    def __init__(self,worker,configuration,program):
        self.program=Program.from_dict(program)
        super().__init__(worker,configuration)

    def get_action(self,env,observation):
        action=super().get_action(env,observation)
        if self.worker.diag_cfg.get('initialization_profile')=='support-probe-restore-1':
            self.diagnostics['evaluator_guard']=self.fsm.last_guard_evaluation
        return action

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
            path=self.base.scene.env_prim_paths[0]+'/'+getattr(asset,'cfg',asset).prim_path.rsplit('/',1)[-1]
            prim=stage.GetPrimAtPath(path)
            if prim and prim.IsValid():
                box=cache.ComputeWorldBound(prim).ComputeAlignedRange()
                geometry[name]={'prim_path':path,'world_bound_min':list(box.GetMin()),
                                'world_bound_max':list(box.GetMax()),
                                'scope':'USD visual/proxy bounds; not measured support contact or collider hull'}
            else:
                geometry[name]={'status':'not_measured','path':path}
        save_json(self.output_dir/'geometry.json',geometry)

        if self.diag_cfg.get('initialization_profile')=='support-probe-restore-1':
            reset=self.env.reset
            def ready_reset(*a,**kw):
                result=reset(*a,**kw)
                from physicalevobench.core.readiness import prepare
                prepare(self)
                return result
            self.env.reset=ready_reset

    def run_episode(self,condition,skill,agent_id,episode_id):
        self.current_condition=condition
        self.ready_directory=self.output_dir/'episodes'/episode_id
        return super().run_episode(condition,skill,agent_id,episode_id)

    def _snapshot(self,phase):
        result=super()._snapshot(phase)
        result['finger_position']=self.as_torch(self.robot.data.joint_pos)[0,self.finger_joint_indices].tolist()
        result['ee_position_world']=self.as_torch(self.base.scene['ee_frame'].data.target_pos_w)[:,0].tolist()
        if self.diag_cfg.get('initialization_profile')=='support-probe-restore-1':
            from physicalevobench.core.readiness import support
            result['evaluator_support']=support(self)
        return result

    def public_task_observation(self):
        if self.diag_cfg.get('task_version') not in ('core-place-public-v3-dev','core-place-public-v4-ready1'):
            return {}
        return {'task_goal_position':list(self.diag_cfg['public_goal']),
                'support_geometry':{'support_contact':'not_measured',
                                    'geometry_source':'see geometry.json; not inferred from reset center'}}
