"""Calibration policies operating in the unchanged joint-position action space."""


class OpenGripper:
    """Known degradation: retain the arm policy but prevent grasp closure."""

    def __init__(self, base_policy, gripper_start):
        self.base_policy, self.gripper_start = base_policy, gripper_start

    def reset(self):
        self.base_policy.reset()

    def get_action(self, env, observation):
        action = self.base_policy.get_action(env, observation).clone()
        action[:, self.gripper_start:] = 1
        return action


class GeometryExpert:
    """Bounded DLS Cartesian FSM, converted to the live JointPositionAction.

    Uses observable geometry, never mass truth. Robot/actuator/solver settings are
    unchanged. An unsuccessful expert is inconclusive about task solvability.
    """

    def __init__(self, worker):
        import torch
        from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg

        self.worker = worker
        self.ik = DifferentialIKController(DifferentialIKControllerCfg(
            command_type='pose', use_relative_mode=False, ik_method='dls'), 1, worker.base.device)
        self.torch = torch
        robot = worker.base.scene['robot']
        self.hand = robot.body_names.index('panda_hand')
        self.joint_ids = [robot.joint_names.index(n) for n in worker.action_mapping['arm_action']['joint_names']]
        self.reset()

    def reset(self):
        self.step = 0
        self.grasp_offset = None

    def get_action(self, env, observation):
        from isaaclab.utils.math import combine_frame_transforms, compute_pose_error, skew_symmetric_matrix

        t, w = self.torch, self.worker
        robot, cube = w.base.scene['robot'], w.base.scene['dex_cube']
        p = w.as_torch(w.base.scene['ee_frame'].data.target_pos_w)[:, 0]
        q = w.as_torch(w.base.scene['ee_frame'].data.target_quat_w)[:, 0]
        obj = w.as_torch(cube.data.root_pos_w)
        target = obj.clone()
        # XYZW convention of pinned Isaac Lab 17; fixed downward grasp.
        orient = t.tensor([[1., 0., 0., 0.]], device=p.device)
        if self.step < 45:
            target[:, 2] += .12
        elif self.step < 100:
            target[:, 2] += .005
        elif self.step < 130:
            target[:, 2] += .005
        else:
            command = w.base.command_manager.get_command('object_pose')
            target, _ = combine_frame_transforms(w.as_torch(robot.data.root_pos_w),
                                                 w.as_torch(robot.data.root_quat_w), command[:, :3])
            if self.grasp_offset is None:
                self.grasp_offset = (p - obj).clone()
            target = target + self.grasp_offset
        # Follow a local Cartesian waypoint; large pose errors must not distort
        # direction through independent per-joint saturation.
        position_error, rotation_error = compute_pose_error(p, q, target, orient)
        local_target = p + position_error * (.025 / position_error.norm(dim=-1, keepdim=True).clamp(min=.025))
        from isaaclab.utils.math import apply_delta_pose

        rotation_step = rotation_error * (.12 / rotation_error.norm(dim=-1, keepdim=True).clamp(min=.12))
        _, local_orientation = apply_delta_pose(p, q, t.cat((t.zeros_like(p), rotation_step), -1))
        self.ik.set_command(t.cat((local_target, local_orientation), -1))
        jac_index = self.hand - 1 if robot.is_fixed_base else self.hand
        jac = w.as_torch(robot.data.body_link_jacobian_w)[:, jac_index, :, self.joint_ids].clone()
        # Shift the hand Jacobian to the exact ee_frame offset, in world coordinates.
        hand_p = w.as_torch(robot.data.body_pos_w)[:, self.hand]
        jac[:, :3] -= t.bmm(skew_symmetric_matrix(p - hand_p), jac[:, 3:])
        current = w.as_torch(robot.data.joint_pos)[:, self.joint_ids]
        desired = self.ik.compute(p, q, jac, current)
        delta = desired-current
        desired = current + delta * (.10/delta.abs().amax(dim=-1, keepdim=True).clamp(min=.10))
        limits = w.as_torch(robot.data.joint_pos_limits)[:, self.joint_ids]
        desired = desired.clamp(limits[..., 0] + .02, limits[..., 1] - .02)
        # The original low-PD arm has gravity enabled. Compensate it through
        # position targets; actuator gains/effort limits remain exactly unchanged.
        gravity = w.as_torch(robot.data.gravity_compensation_forces)[:, self.joint_ids]
        stiffness = w.as_torch(robot.data.joint_stiffness)[:, self.joint_ids]
        desired = desired + gravity / stiffness
        self.diagnostics = {'ee_position':p.tolist(), 'target_position':target.tolist(),
                            'gravity_compensation_torque':gravity.tolist(),
                            'live_joint_stiffness':stiffness.tolist()}
        term = w.base.action_manager.get_term('arm_action')
        action = t.zeros((1, 8), device=p.device)
        action[:, w.arm_slice] = (desired - term._offset) / term._scale
        action[:, 7] = 1 if self.step < 100 else -1
        self.step += 1
        return action
