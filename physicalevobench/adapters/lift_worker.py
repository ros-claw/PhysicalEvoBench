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
    def __init__(self, checkpoint, output_dir, record_camera_video=False):
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
        definition = LiftObjectEnvironment().build(LiftObjectEnvironmentCfg(
            enable_cameras=record_camera_video
        ))
        variation = definition.scene.assets["dex_cube"].get_variation("mass")
        variation.apply_cfg(ObjectMassVariationCfg(
            sampler_cfg=UniformSamplerCfg(low=[0.1], high=[0.1]), recompute_inertia=True
        ))
        variation.enable()
        self.mass_sampler = variation.sampler
        self.env = ArenaEnvBuilder(
            definition, ArenaEnvBuilderCfg(num_envs=1, device="cuda:0", presets="physx")
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
        maximum_delta = 0.0
        maximum_action = 0.0
        joint_violations = 0
        steps = 0
        frames = []
        with (directory / "trace.jsonl").open("w") as trace:
            for step in range(self.base.max_episode_length + 1):
                with torch.inference_mode():
                    raw = self.policy.get_action(self.env, observation)
                    action = raw.clone()
                    action[:, self.arm_slice] *= skill.arm_action_gain
                    if not torch.isfinite(action).all():
                        raise RuntimeError("Nonfinite action: infrastructure failure, not task failure")
                    if ((action < self.action_low) | (action > self.action_high)).any():
                        raise RuntimeError("Action outside the live environment action space")
                    joints = self.as_torch(robot.data.joint_pos)
                    limits = self.as_torch(robot.data.joint_pos_limits)
                    joint_violations += int(((joints < limits[..., 0] - 1e-3)
                                             | (joints > limits[..., 1] + 1e-3)).sum().item())
                    delta = float((action - raw).abs().max().item())
                    maximum_delta = max(maximum_delta, delta)
                    maximum_action = max(maximum_action, float(action.abs().max().item()))
                    if self.record_camera_video:
                        camera = next(iter(observation["camera_obs"].values()))
                        frames.append(camera[0, ..., :3].detach().cpu().numpy())
                    trace.write(json.dumps({"step": step, "raw_action": tensor_json(raw),
                                            "applied_action": tensor_json(action),
                                            "observation": tensor_json({k: v for k, v in observation.items()
                                                                        if k != "camera_obs"}),
                                            "joint_position": tensor_json(joints),
                                            "object_position": tensor_json(self.as_torch(cube.data.root_pos_w))},
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
