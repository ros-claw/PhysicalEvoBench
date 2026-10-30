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
    def _snapshot(self,phase):
        result=super()._snapshot(phase)
        result['finger_position']=self.as_torch(self.robot.data.joint_pos)[0,self.finger_joint_indices].tolist()
        result['ee_position_world']=self.as_torch(self.base.scene['ee_frame'].data.target_pos_w)[:,0].tolist()
        return result

    def public_task_observation(self):
        if self.diag_cfg.get('task_version')!='core-place-public-v3-dev':
            return {}
        return {'task_goal_position':list(self.diag_cfg['public_goal']),
                'support_geometry':{'plane_z_m':0.,'object_half_extent_m':.02,
                                    'support_contact':'not_measured'}}
