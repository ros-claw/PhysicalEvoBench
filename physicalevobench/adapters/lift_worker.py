"""Trusted real-physics rollouts. Construct only after Arena's SimulationAppContext starts."""

import json
from pathlib import Path

from physicalevobench.doctor import save_json, sha256


def tensor_json(value):
    if hasattr(value, "items"):
        return {key: tensor_json(item) for key, item in value.items()}
    if hasattr(value, "detach"):
        return value.detach().cpu().tolist()
    return value


class LiftWorker:
    def __init__(self, checkpoint, output_dir, record_camera_video=False, stability_mode=False):
        import torch

        from isaaclab_arena.environments.arena_env_builder import ArenaEnvBuilder
        from isaaclab_arena.environments.arena_env_builder_cfg import ArenaEnvBuilderCfg
        from isaaclab_arena.policy.rsl_rl_action_policy import RslRlActionPolicy, RslRlActionPolicyCfg
        from isaaclab_arena.variations.object_mass_variation import ObjectMassVariationCfg
        from isaaclab_arena.variations.uniform_sampler import UniformSamplerCfg
        from isaaclab_arena_environments.lift_object_environment import (
            LiftObjectEnvironment,
            LiftObjectEnvironmentCfg,
        )

        self.output_dir = Path(output_dir)
        self.checkpoint = Path(checkpoint)
        self.checkpoint_hash = sha256(checkpoint)
        self.record_camera_video = record_camera_video
        self.stability_mode = stability_mode
        definition = LiftObjectEnvironment().build(LiftObjectEnvironmentCfg(
            enable_cameras=record_camera_video, rl_training_mode=stability_mode
        ))
        variation = definition.scene.assets["dex_cube"].get_variation("mass")
        variation.apply_cfg(ObjectMassVariationCfg(
            sampler_cfg=UniformSamplerCfg(low=[0.1], high=[0.1]), recompute_inertia=True
        ))
        variation.enable()
        self.mass_sampler = variation.sampler
        self.env = ArenaEnvBuilder(
            definition, ArenaEnvBuilderCfg(
                num_envs=1, device="cuda:0", presets="physx",
                recorder_dataset_export_dir_path=str(self.output_dir / "recorder"),
                recorder_dataset_filename="dataset",
            )
        ).make_registered()
        self.base = self.env.unwrapped
        # ManagerBase deep-copies configs; mutate the sampler actually owned by the live event.
        self.mass_sampler = self.base.event_manager.get_term_cfg(
            "dex_cube_mass_variation"
        ).params["sampler"]
        self.policy = RslRlActionPolicy(RslRlActionPolicyCfg(
            checkpoint_path=str(checkpoint), device="cuda:0"
        ))
        self.policy.set_task_description(self.base.get_language_instruction())
        manager = self.base.action_manager
        mapping = {}
        offset = 0
        for name, dimension in zip(manager.active_terms, manager.action_term_dim, strict=True):
            term = manager.get_term(name)
            descriptor = term.IO_descriptor
            mapping[name] = {"start": offset, "stop": offset + dimension,
                             "joint_names": list(descriptor.joint_names),
                             "term_class": type(term).__name__}
            offset += dimension
        if "arm_action" not in mapping or "gripper_action" not in mapping:
            raise RuntimeError("Unverified Franka action mapping")
        if mapping["arm_action"]["term_class"] != "JointPositionAction":
            raise RuntimeError("Skill gain requires joint-position actions")
        arm = mapping["arm_action"]
        self.arm_slice = slice(arm["start"], arm["stop"])
        finger_names = mapping["gripper_action"]["joint_names"]
        self.finger_joint_indices = [self.base.scene["robot"].joint_names.index(name) for name in finger_names]
        if len(self.finger_joint_indices) != 2:
            raise RuntimeError("Expected two named Franka finger joints")
        mapping["gripper_action"]["joint_indices"] = self.finger_joint_indices
        self.action_mapping = mapping
        self.action_low = torch.as_tensor(self.base.single_action_space.low, device=self.base.device)
        self.action_high = torch.as_tensor(self.base.single_action_space.high, device=self.base.device)
        save_json(self.output_dir / "action_mapping.json", mapping)

    @staticmethod
    def as_torch(value):
        import torch
        import warp as wp

        if torch.is_tensor(value):
            return value
        if hasattr(value, "torch"):
            return value.torch
        return wp.to_torch(value)

    def run_episode(self, condition, skill, agent_id, episode_id):
        import torch

        # Env.step creates inference tensors in command/metric caches. Explicit resets must
        # use the same mode when a persistent environment is reused across conditions.
        with torch.inference_mode():
            return self._run_episode(condition, skill, agent_id, episode_id)

    def _run_episode(self, condition, skill, agent_id, episode_id):
        import torch

        if skill.base_checkpoint_sha256 != self.checkpoint_hash or sha256(self.checkpoint) != self.checkpoint_hash:
            raise RuntimeError("Frozen checkpoint changed")
        directory = self.output_dir / "episodes" / episode_id
        directory.mkdir(parents=True, exist_ok=False)
        self.mass_sampler.low.fill_(condition["object_mass_kg"])
        self.mass_sampler.high.fill_(condition["object_mass_kg"])
        raw_path = directory / "upstream.jsonl"
        self.base.episode_recorder.set_output_path(raw_path)
        observation, _ = self.env.reset(seed=condition["seed"])
        self.policy.reset()
        cube = self.base.scene["dex_cube"]
        robot = self.base.scene["robot"]
        mass = self.as_torch(cube.data.body_mass).clone()
        inertia = self.as_torch(cube.data.body_inertia).clone()
        requested = torch.full_like(mass, condition["object_mass_kg"])
        torch.testing.assert_close(mass, requested, atol=1e-6, rtol=1e-6)
        initial = {"condition": condition, "mass_readback_kg": tensor_json(mass),
                   "inertia_readback": tensor_json(inertia),
                   "joint_position": tensor_json(self.as_torch(robot.data.joint_pos)),
                   "joint_limits": tensor_json(self.as_torch(robot.data.joint_pos_limits)),
                   "object_position": tensor_json(self.as_torch(cube.data.root_pos_w)),
                   "object_orientation": tensor_json(self.as_torch(cube.data.root_quat_w)),
                   "target_command": tensor_json(self.base.command_manager.get_command("object_pose"))}
        save_json(directory / "initial_state.json", initial)
        save_json(directory / "skill.json", {**skill.to_dict(), "skill_sha256": skill.sha256})
        controller = skill.make_controller(self.action_mapping) if hasattr(skill, "make_controller") else None
        maximum_delta = 0.0
        maximum_action = 0.0
        joint_violations = 0
        steps = 0
        frames = []
        safety_positions = []
        stability_samples = []
        with (directory / "trace.jsonl").open("w") as trace:
            for step in range(self.base.max_episode_length + 1):
                with torch.inference_mode():
                    raw = self.policy.get_action(self.env, observation)
                    action = raw.clone()
                    proprioception = None
                    if controller is not None and getattr(controller, "uses_proprioception", False):
                        q = self.as_torch(robot.data.joint_pos)[0, self.finger_joint_indices]
                        v = self.as_torch(robot.data.joint_vel)[0, self.finger_joint_indices]
                        low = self.as_torch(robot.data.joint_pos_limits)[0, self.finger_joint_indices, 0]
                        proprioception = {"finger_position": q.tolist(), "finger_velocity": v.tolist(),
                                          "finger_lower_limits": low.tolist(), "step_dt": self.base.step_dt}
                    if controller is None:
                        action[:, self.arm_slice] *= skill.arm_action_gain
                    else:
                        transformed = (controller.apply(raw[0].tolist(), step, proprioception)
                                       if proprioception is not None else controller.apply(raw[0].tolist(), step))
                        action = torch.tensor([transformed], dtype=raw.dtype, device=raw.device)
                    if not torch.isfinite(action).all():
                        raise RuntimeError("Nonfinite action: infrastructure failure, not task failure")
                    if ((action < self.action_low) | (action > self.action_high)).any():
                        raise RuntimeError("Action outside the live environment action space")
                    joints = self.as_torch(robot.data.joint_pos)
                    limits = self.as_torch(robot.data.joint_pos_limits)
                    safety_positions.append(joints[0].tolist())
                    joint_violations += int(((joints < limits[..., 0] - 1e-3)
                                             | (joints > limits[..., 1] + 1e-3)).sum().item())
                    delta = float((action - raw).abs().max().item())
                    maximum_delta = max(maximum_delta, delta)
                    maximum_action = max(maximum_action, float(action.abs().max().item()))
                    if self.record_camera_video:
                        camera = next(iter(observation["camera_obs"].values()))
                        frames.append(camera[0, ..., :3].detach().cpu().numpy())
                    stability_state = {}
                    if self.stability_mode:
                        from isaaclab.utils.math import combine_frame_transforms
                        from isaaclab.managers import SceneEntityCfg
                        from isaaclab_arena.tasks.terminations import lift_object_rl_success

                        root_p = self.as_torch(robot.data.root_pos_w)
                        root_q = self.as_torch(robot.data.root_quat_w)
                        command = self.base.command_manager.get_command("object_pose")
                        goal, _ = combine_frame_transforms(root_p, root_q, command[:, :3])
                        stability_state = {
                            "object_velocity": tensor_json(self.as_torch(cube.data.root_vel_w)),
                            "goal_position_world": tensor_json(goal),
                            "robot_root_position": tensor_json(root_p),
                            "robot_root_orientation": tensor_json(root_q),
                            "target_command": tensor_json(command),
                            "step_dt": self.base.step_dt,
                            "instant_predicate": bool(lift_object_rl_success(
                                self.base, object_cfg=SceneEntityCfg("dex_cube"),
                                rl_training=False)[0]),
                        }
                        stability_samples.append({**stability_state, "object_position":
                                                  tensor_json(self.as_torch(cube.data.root_pos_w))})
                    trace.write(json.dumps({"step": step, "raw_action": tensor_json(raw),
                                            "applied_action": tensor_json(action),
                                            "controller_proprioception": proprioception,
                                            "policy_diagnostics": getattr(self.policy, "diagnostics", None),
                                            "observation": tensor_json({k: v for k, v in observation.items()
                                                                        if k != "camera_obs"}),
                                            "joint_position": tensor_json(joints),
                                            "joint_velocity": tensor_json(self.as_torch(robot.data.joint_vel)),
                                            "ee_position": tensor_json(self.as_torch(self.base.scene["ee_frame"].data.target_pos_w)),
                                            "object_position": tensor_json(self.as_torch(cube.data.root_pos_w)),
                                            **stability_state},
                                           allow_nan=False) + "\n")
                    observation, _, terminated, truncated, _ = self.env.step(action)
                    steps += 1
                    if bool(terminated.any() or truncated.any()):
                        break
            else:
                raise RuntimeError("Official episode did not terminate at its configured limit")
        raw_records = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
        finished = [row for row in raw_records if row.get("episode_length", 0) > 0]
        if len(finished) != 1 or finished[0]["episode_length"] != steps:
            raise RuntimeError("Completed episode evidence does not match actual action trace")
        official = finished[0]
        if type(official["success"]) is not bool:
            raise RuntimeError("Missing upstream task outcome")
        row = {"schema_version": "0.1", "run_id": self.output_dir.name,
               "episode_id": episode_id, "condition_id": condition["condition_id"],
               "split": condition["split"], "seed": condition["seed"], "agent_id": agent_id,
               "environment_id": "PEB-Lift-Mass-v0", "execution_status": "OK",
               "base_checkpoint_sha256": self.checkpoint_hash, "skill_sha256": skill.sha256,
               "success": official["success"], "steps": steps,
               "simulated_seconds": steps * self.base.step_dt,
               "termination_reason": "success" if official["success"] else
               ("timeout" if bool(truncated.any()) else "task_failure"),
               "failure_type": None if official["success"] else "task_not_completed",
               "unsafe_action_count": 0, "unsafe_action_rule": "finite and live action-space bounds",
               "joint_limit_violation_count": joint_violations,
               "joint_limit_rule": "pre-step position outside live hard limits by > 0.001 coordinate units (rad or m)",
               "collision_count": None, "maximum_action_abs": maximum_action,
               "maximum_action_change_abs": maximum_delta,
               "initial_state_artifact": str((directory / "initial_state.json").relative_to(self.output_dir)),
               "trace_artifact": str((directory / "trace.jsonl").relative_to(self.output_dir)),
               "upstream_artifact": str(raw_path.relative_to(self.output_dir)), "video_artifact": None,
               "ignored_zero_step_resets": len(raw_records) - len(finished)}
        from physicalevobench.calibration.safety import summarize_safety

        safety = summarize_safety(safety_positions, initial["joint_limits"][0],
                                  robot.joint_names, self.base.step_dt)
        if safety["violation_joint_samples"] != joint_violations:
            raise RuntimeError("Safety diagnostic disagrees with historical count")
        save_json(directory / "sampled_safety.json", safety)
        if self.stability_mode:
            from physicalevobench.stability.metrics import holding_metrics

            metric = holding_metrics(stability_samples)
            row.update(environment_id="PEB-Lift-Mass-Stability-v1", upstream_success=official["success"],
                       success=metric["stable_success"], stability=metric)
            save_json(directory / "holding.json", metric)
        save_json(directory / "episode.json", row)
        if frames:
            import imageio.v2 as imageio

            video = directory / "wrist_camera.mp4"
            with imageio.get_writer(str(video), fps=round(1 / self.base.step_dt),
                                    macro_block_size=1) as writer:
                for frame in frames:
                    writer.append_data(frame)
            row["video_artifact"] = str(video.relative_to(self.output_dir))
            save_json(directory / "episode.json", row)
        print(json.dumps(row), flush=True)
        return row

    def close(self):
        self.env.close()
