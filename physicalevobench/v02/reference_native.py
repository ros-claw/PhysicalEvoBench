"""State-based DLS teacher in the common physical target envelope."""

from physicalevobench.calibration.policies import GeometryExpert, OpenGripper
from physicalevobench.v02.reference import BoundedJointIntegral, ReferenceConfig, ReferenceFSM


class StateBasedReference(GeometryExpert):
    def __init__(self, worker, configuration):
        self.configuration = ReferenceConfig(**configuration)
        super().__init__(worker)

    def reset(self):
        super().reset()
        self.fsm = ReferenceFSM(self.configuration)
        self.integral = BoundedJointIntegral(self.configuration.joint_integral_gain_s,
                                             self.configuration.joint_integral_limit_rad)

    def get_action(self, env, observation):
        from isaaclab.utils.math import (
            apply_delta_pose, combine_frame_transforms, compute_pose_error, skew_symmetric_matrix,
        )

        t,w = self.torch,self.worker
        robot,cube = w.base.scene['robot'],w.base.scene['dex_cube']
        p = w.as_torch(w.base.scene['ee_frame'].data.target_pos_w)[:,0]
        q = w.as_torch(w.base.scene['ee_frame'].data.target_quat_w)[:,0]
        obj = w.as_torch(cube.data.root_pos_w)
        orient = t.tensor([[1.,0.,0.,0.]],device=p.device)
        _,orientation_error = compute_pose_error(p,q,p,orient)
        goal,_ = combine_frame_transforms(w.as_torch(robot.data.root_pos_w),
                                          w.as_torch(robot.data.root_quat_w),
                                          w.base.command_manager.get_command('object_pose')[:,:3])
        contacts = []
        for side in ('left','right'):
            value = w.as_torch(w.base.scene['v02_contact_'+side].data.normal_force_matrix_w)
            contacts.append(float(value.reshape(-1,3).norm(dim=-1).max()))
        public = {'ee_position':p[0].tolist(),'object_position':obj[0].tolist(),
                  'ee_quaternion_xyzw':q[0].tolist(),
                  'goal_position':goal[0].tolist(),
                  'object_velocity':w.as_torch(cube.data.root_vel_w)[0,:3].tolist(),
                  'finger_position':w.as_torch(robot.data.joint_pos)[0,w.finger_joint_indices].tolist(),
                  'orientation_error':float(orientation_error.norm()),'cube_contact_force':contacts}
        if hasattr(w,'public_task_observation'):
            public.update(w.public_task_observation())
        decision = self.fsm.update(public,w.base.step_dt)
        target = t.tensor([decision['target_position']],device=p.device)
        position_error,rotation_error = compute_pose_error(p,q,target,orient)
        local_target = p+position_error*(.025/position_error.norm(dim=-1,keepdim=True).clamp(min=.025))
        rotation_step = rotation_error*(.12/rotation_error.norm(dim=-1,keepdim=True).clamp(min=.12))
        _,local_orientation = apply_delta_pose(p,q,t.cat((t.zeros_like(p),rotation_step),-1))
        self.ik.set_command(t.cat((local_target,local_orientation),-1))
        jac_index = self.hand-1 if robot.is_fixed_base else self.hand
        jac = w.as_torch(robot.data.body_link_jacobian_w)[:,jac_index,:,self.joint_ids].clone()
        hand_p = w.as_torch(robot.data.body_pos_w)[:,self.hand]
        jac[:,:3] -= t.bmm(skew_symmetric_matrix(p-hand_p),jac[:,3:])
        current = w.as_torch(robot.data.joint_pos)[:,self.joint_ids]
        desired = self.ik.compute(p,q,jac,current)
        delta = desired-current
        delta = delta*(.10/delta.abs().amax(dim=-1,keepdim=True).clamp(min=.10))
        active=decision['phase'] in ('lift','hold')
        if w.diag_cfg.get('control_profile')=='contact-integral-v1':
            active=min(contacts)>=.5 and sum(public['finger_position'])/2<.035
            if active:
                bias=self.integral.update(delta[0].tolist(),w.base.step_dt,True)
            else:
                # Fixed continuous unloading, independent of participant phase names.
                import math
                self.integral.value=[v*math.exp(-w.base.step_dt/.2) for v in self.integral.value]
                bias=list(self.integral.value)
        else:
            bias = self.integral.update(delta[0].tolist(),w.base.step_dt,active)
        desired = current+delta
        limits = w.as_torch(robot.data.joint_pos_limits)[:,self.joint_ids]
        desired = desired.clamp(limits[...,0]+.02,limits[...,1]-.02)
        gravity = w.as_torch(robot.data.gravity_compensation_forces)[:,self.joint_ids]
        stiffness = w.as_torch(robot.data.joint_stiffness)[:,self.joint_ids]
        desired = desired+gravity/stiffness+t.tensor([bias],device=p.device)
        term = w.base.action_manager.get_term('arm_action')
        action = t.zeros((1,8),device=p.device)
        action[:,w.arm_slice] = (desired-term._offset)/term._scale
        action[:,w.action_mapping['gripper_action']['start']] = 1 if decision['gripper']=='open' else -1
        self.diagnostics = {'reference_schema':'state-reference-1','control_profile':w.diag_cfg.get('control_profile','phase-integral-legacy'),'public':public,**decision,
                            'decision':decision,
                            'bounded_joint_integral_rad':bias,'joint_error_feedback_rad':delta[0].tolist(),
                            'ee_position':p.tolist(),'target_position':target.tolist()}
        self.step += 1
        return action


class OpenReference(OpenGripper):
    def get_action(self, env, observation):
        action = super().get_action(env,observation)
        self.diagnostics = self.base_policy.diagnostics
        return action
