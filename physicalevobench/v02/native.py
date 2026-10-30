"""Instrumented native diagnosis. Import only after SimulationApp starts."""

import gzip
import json

from physicalevobench.adapters.lift_worker import LiftWorker, tensor_json
from physicalevobench.doctor import save_json
from physicalevobench.stability.audit import world_goal
from physicalevobench.v02.execution import TargetEnvelope


def hard_boundary(env, finger_depth=.01, arm_depth=.1):
    import torch

    robot = env.scene['robot']
    q = LiftWorker.as_torch(robot.data.joint_pos)
    limits = LiftWorker.as_torch(robot.data.joint_pos_limits)
    thresholds = torch.tensor([finger_depth if 'finger' in n else arm_depth for n in robot.joint_names],
                              device=q.device)
    depth = torch.maximum(limits[..., 0]-q, q-limits[..., 1])
    return (~torch.isfinite(q)).any(dim=1) | (depth > thresholds).any(dim=1)


class DiagnosticWorker(LiftWorker):
    def __init__(self, checkpoint, output_dir, cfg):
        self.diag_cfg = cfg
        self.recording = False
        self.frames, self.controls, self.terminal = [], [], None

        def transform(definition):
            callback = definition.env_cfg_callback

            def configure(env_cfg):
                from isaaclab.managers import TerminationTermCfg
                from isaaclab.sensors import ContactSensorCfg

                if callback:
                    env_cfg = callback(env_cfg)
                if 'horizon_s' in self.diag_cfg:
                    horizon = self.diag_cfg['horizon_s']
                    if not ((horizon in (5.,10.) and self.diag_cfg.get('task_version') == f'state-reference-h{horizon:g}-v1') or
                            (horizon==20. and self.diag_cfg.get('core_task')=='place' and
                             self.diag_cfg.get('task_version') in ('core-place-h20-v2-dev','core-place-public-v3-dev','core-place-public-v4-ready1')) or
                            (horizon==1. and self.diag_cfg.get('task_version')=='esl-initialization-diagnostic-v1')):
                        raise ValueError('Reference horizon must have a distinct registered task version')
                    env_cfg.episode_length_s = horizon
                env_cfg.terminations.v02_hard_boundary = TerminationTermCfg(func=hard_boundary)
                env_cfg.scene.robot.spawn.activate_contact_sensors = True
                for label, body in [('left', 'panda_leftfinger'), ('right', 'panda_rightfinger')]:
                    setattr(env_cfg.scene, 'v02_contact_'+label, ContactSensorCfg(
                        prim_path=env_cfg.scene.robot.prim_path+'/'+body, update_period=0., history_length=1,
                        filter_prim_paths_expr=[env_cfg.scene.dex_cube.prim_path]))
                if self.diag_cfg.get('initialization_profile')=='support-probe-restore-1':
                    env_cfg.sim.enable_scene_query_support=True
                    env_cfg.scene.dex_cube.spawn.activate_contact_sensors=True
                    env_cfg.scene.esl_support=ContactSensorCfg(prim_path=env_cfg.scene.dex_cube.prim_path,
                        update_period=0.,history_length=1)
                if self.diag_cfg.get('diagnostic_disable_table_collision'):
                    from physicalevobench.core.scene_diagnostics import spawn_table_without_collision
                    env_cfg.scene.table.spawn.diagnostic_original_spawn=env_cfg.scene.table.spawn.func
                    env_cfg.scene.table.spawn.func=spawn_table_without_collision
                env_cfg.compute_final_obs = True
                return env_cfg

            definition.env_cfg_callback = configure
            return definition

        super().__init__(checkpoint, output_dir, stability_mode=cfg['mode']=='FixedHorizonDiagnostic',
                         action_limit=1000., environment_transform=transform,
                         state_execution_sha256=cfg.get('state_execution_sha256'))
        self.robot = self.base.scene['robot']
        names = list(self.robot.joint_names)
        self.bounds = self.as_torch(self.robot.data.joint_pos_limits)[0].tolist()
        self.velocity_limits = self.as_torch(self.robot.data.joint_vel_limits)[0].tolist()
        self.layer = TargetEnvelope(names, self.bounds, self.velocity_limits, self.base.step_dt)
        self.joint_indices = {name: [names.index(n) for n in term['joint_names']]
                              for name, term in self.action_mapping.items()}
        self._install_hooks()
        self._metadata()

    def _optional(self, obj, name):
        try:
            return {'value': tensor_json(self.as_torch(getattr(obj, name))), 'source': name}
        except (AttributeError, RuntimeError, TypeError) as error:
            return {'value': None, 'status': 'NOT_MEASURED', 'reason': str(error)[:160]}

    def _metadata(self):
        import omni.usd
        from pxr import UsdGeom

        terms = {}
        for name in self.action_mapping:
            term = self.base.action_manager.get_term(name)
            terms[name] = {'class': type(term).__name__, 'mapping': self.action_mapping[name],
                           'scale': tensor_json(getattr(term, '_scale', None)),
                           'offset': tensor_json(getattr(term, '_offset', None)),
                           'open_command': tensor_json(getattr(term, '_open_command', None)),
                           'close_command': tensor_json(getattr(term, '_close_command', None))}
        stage = omni.usd.get_context().get_stage()
        joints = []
        for prim in stage.Traverse():
            if '/env_0/' in str(prim.GetPath()) and 'Joint' in prim.GetTypeName():
                joints.append({'path': str(prim.GetPath()), 'type': prim.GetTypeName(),
                               'schemas': list(prim.GetAppliedSchemas()),
                               'relationships': {r.GetName(): [str(p) for p in r.GetTargets()]
                                                 for r in prim.GetRelationships()},
                               'attributes': {a.GetName(): str(a.Get()) for a in prim.GetAttributes()
                                              if any(t in a.GetName().lower() for t in ('limit', 'axis', 'drive', 'mimic'))}})
        semantics = {'schema': 'v02-control-semantics', 'mode': self.diag_cfg['mode'],
                     'execution_layer': self.diag_cfg['execution_layer'], 'action_terms': terms,
                     'joint_names': list(self.robot.joint_names), 'hard_limits': self.bounds,
                     'soft_limits': self._optional(self.robot.data, 'soft_joint_pos_limits'),
                     'solver_velocity_limits': self.velocity_limits,
                     'solver_effort_limits': self._optional(self.robot.data, 'joint_effort_limits'),
                     'physics_dt': self.base.physics_dt, 'control_dt': self.base.step_dt,
                     'decimation': self.base.cfg.decimation,
                     'backend_handles_decimation': self.base._physics_handles_decimation,
                     'stage_metres_per_unit': UsdGeom.GetStageMetersPerUnit(stage), 'usd_joints': joints,
                     'unit_conventions': {'live_revolute': 'radians', 'usd_revolute_limits': 'degrees',
                                          'live_prismatic': 'metres', 'usd_prismatic': 'stage units'},
                     'actuators': {k: str(v) for k, v in self.robot.cfg.actuators.items()},
                     'hard_boundary': {'finger_depth_m': .01, 'arm_depth_rad': .1},
                     'target_rate_caps': {'arm_rad_s': 1., 'finger_m_s': .04},
                     'force_scope': 'ContactSensor net-normal and cube-filtered normal forces; tangential NOT_MEASURED',
                     'pair_force_kind': 'PhysX pair force is normal_force_matrix_w; tangential force NOT_MEASURED',
                     'state_hook': 'scene.update after original, and recorder.record_pre_reset before autoreset'}
        if 'task_version' in self.diag_cfg:
            semantics.update(task_version=self.diag_cfg['task_version'],horizon_s=self.base.max_episode_length_s,
                             reference_config=self.diag_cfg['reference_config'])
        save_json(self.output_dir/'control_semantics.json', semantics)

    def _snapshot(self, phase):
        cube = self.base.scene['dex_cube']
        command = self.base.command_manager.get_command('object_pose')
        goal = world_goal(self.as_torch(self.robot.data.root_pos_w)[0].tolist(),
                          self.as_torch(self.robot.data.root_quat_w)[0].tolist(), command[0, :3].tolist())
        contacts = {}
        for name in ('left', 'right'):
            sensor = self.base.scene['v02_contact_'+name]
            contacts[name] = {'net_force_w': self._optional(sensor.data, 'net_normal_forces_w'),
                              'cube_force_matrix_w': self._optional(sensor.data, 'normal_force_matrix_w')}
        return {'phase': phase, 'control_step': len(self.controls)-1,
                'physics_step_global': self.base._sim_step_counter,
                'joint_position': tensor_json(self.as_torch(self.robot.data.joint_pos)),
                'joint_velocity': tensor_json(self.as_torch(self.robot.data.joint_vel)),
                'object_position': tensor_json(self.as_torch(cube.data.root_pos_w)),
                'object_velocity': tensor_json(self.as_torch(cube.data.root_vel_w)),
                'target_command': tensor_json(command), 'goal_position_world': [goal],
                'applied_torque': self._optional(self.robot.data, 'applied_torque'),
                'computed_torque': self._optional(self.robot.data, 'computed_torque'),
                'contacts': contacts}

    def _install_hooks(self):
        process = self.base.action_manager.process_action

        def processed(action):
            process(action)
            if not self.recording:
                return
            targets = [None]*len(self.robot.joint_names)
            for name, indices in self.joint_indices.items():
                term = self.base.action_manager.get_term(name)
                for index, value in zip(indices, term.processed_actions[0].tolist(), strict=True):
                    targets[index] = value
            constrained = self.layer.apply(targets) if self.diag_cfg['execution_layer']=='TargetBounded' else {
                'processed_target': targets, 'applied_target': targets, 'limited_joints': [],
                'initial_state_rate_conflicts': []}
            if self.diag_cfg['execution_layer']=='TargetBounded':
                import torch

                for name, indices in self.joint_indices.items():
                    term = self.base.action_manager.get_term(name)
                    term._processed_actions[:] = torch.tensor(
                        [[constrained['applied_target'][i] for i in indices]], device=action.device)
            actual_targets = [None]*len(self.robot.joint_names)
            for name, indices in self.joint_indices.items():
                term = self.base.action_manager.get_term(name)
                for index, value in zip(indices, term.processed_actions[0].tolist(), strict=True):
                    actual_targets[index] = value
            constrained['requested_bounded_target'] = constrained['applied_target']
            constrained['applied_target'] = actual_targets
            if self.diag_cfg['execution_layer']=='TargetBounded':
                self.layer.previous = actual_targets
            self.controls.append({'control_step': len(self.controls),
                                  'network_proposal': tensor_json(self.last_network_proposal),
                                  'accepted_raw_action': tensor_json(action), **constrained})

        self.base.action_manager.process_action = processed
        policy_action = self.policy.get_action

        def propose(env, observation):
            value = policy_action(env, observation)
            self.last_network_proposal = value.clone()
            return value

        self.policy.get_action = propose
        update = self.base.scene.update

        def after_update(dt):
            update(dt)
            if self.recording:
                self.frames.append(self._snapshot('post_physics'))

        self.base.scene.update = after_update
        pre_reset = self.base.recorder_manager.record_pre_reset

        def before_reset(env_ids, *args, **kwargs):
            if self.recording:
                self.terminal = self._snapshot('terminal_pre_reset')
                self.terminal['terminated'] = tensor_json(self.base.reset_terminated)
                self.terminal['truncated'] = tensor_json(self.base.reset_time_outs)
                self.terminal['hard_boundary'] = tensor_json(hard_boundary(self.base))
                self.recording = False
            return pre_reset(env_ids, *args, **kwargs)

        self.base.recorder_manager.record_pre_reset = before_reset
        reset = self.env.reset

        def after_reset(*args, **kwargs):
            result = reset(*args, **kwargs)
            self.layer.reset(self.as_torch(self.robot.data.joint_pos)[0].tolist())
            if self.diag_cfg['mode']=='FixedHorizonDiagnostic':
                self.base.command_manager.get_term('object_pose').time_left.fill_(float('inf'))
            self.initial_capture = self._snapshot('initial_post_reset')
            self.recording = True
            return result

        self.env.reset = after_reset

    def run_episode(self, condition, skill, agent_id, episode_id):
        self.recording = False
        self.frames, self.controls, self.terminal = [], [], None
        row = super().run_episode(condition, skill, agent_id, episode_id)
        if self.terminal is None or len(self.controls) != row['steps']:
            raise RuntimeError('Terminal pre-reset capture or action coverage missing')
        directory = self.output_dir/'episodes'/episode_id
        save_json(directory/'initial_capture.json', self.initial_capture)
        save_json(directory/'terminal_pre_reset.json', self.terminal)
        for filename, data in [('controls', self.controls), ('physics', self.frames)]:
            with gzip.open(directory/(filename+'.jsonl.gz'), 'wt') as stream:
                for sample in data:
                    stream.write(json.dumps(sample, allow_nan=False)+'\n')
        from physicalevobench.v02.audit import episode_metrics

        metrics = episode_metrics(directory, self.output_dir/'control_semantics.json')
        if self.diag_cfg['mode'] == 'FixedHorizonDiagnostic':
            row['success'] = metrics['holding']['stable_success']
            row['termination_reason'] = ('hard_boundary' if metrics['hard_boundary_terminated'] else
                                         ('horizon' if self.terminal['truncated'][0] else 'task_failure'))
            row['failure_type'] = None if row['success'] else 'effective_task_not_completed'
        row.update(schema_version='0.2-diagnostic',
                   environment_id='PEB-Lift-v02-'+self.diag_cfg['mode']+'-'+self.diag_cfg['execution_layer'],
                   diagnostic=metrics, terminal_pre_reset_artifact=str((directory/'terminal_pre_reset.json').relative_to(self.output_dir)))
        if 'task_version' in self.diag_cfg:
            row['environment_id'] += '-'+self.diag_cfg['task_version']
        save_json(directory/'episode.json', row)
        return row
