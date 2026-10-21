# Locked upstream API inspection

Inspected commit: `c7edf3a9d5d8276565208f72422f8f8a0806d6cf`.

| Item | Source and behavior |
| --- | --- |
| Task factory | `isaaclab_arena_environments/lift_object_environment.py`: defaults to `dex_cube`, `franka_joint_pos`, evaluation mode; 50 Hz callback, 5-second episodes |
| Policy | `isaaclab_arena/policy/rsl_rl_action_policy.py`: typed `RslRlActionPolicyCfg`; reads neighboring `params/agent.yaml`; lazy runner loading |
| Joint actions | `isaaclab_arena/embodiments/franka/franka.py`: named `arm_action` JointPositionActionCfg and `gripper_action` BinaryJointPositionActionCfg; resolve slices from live action manager before adapting |
| Mass | `isaaclab_arena/variations/object_mass_variation.py`: reset event `ApplyObjectMassFromSampler`, `set_masses_index`, inertia scaling against original defaults |
| Results | `isaaclab_arena/evaluation/policy_runner.py`: episode recorder outputs `episode_results_rank0.jsonl` under timestamped output directory |
| Lifecycle | `SimulationAppContext` must launch before simulation-dependent imports; `ISAACLAB_ARENA_FORCE_EXIT_ON_COMPLETE=1` avoids shutdown hang |

Mass catalogue names, physical mass readback, action mapping, checkpoint compatibility and
success criteria still require runtime verification. The source inspection is not an integration pass.
