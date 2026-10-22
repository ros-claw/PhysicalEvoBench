"""Independently reconstruct temporal commands from saved raw policy actions."""

import math
import struct

from physicalevobench.evaluation.audit import near, read_jsonl
from physicalevobench.evaluation.confirmation_audit import load
from physicalevobench.protocols.temporal_skill import TemporalSkill


def audit_temporal_episode(root, row, condition, mapping):
    if row.get("synthetic_fixture") or row["execution_status"] != "OK":
        raise ValueError("Invalid physical evidence")
    if row["seed"] != condition["seed"] or row["split"] != condition["split"]:
        raise ValueError("Episode differs from registered condition")
    paths = {key: (root / row[key]).resolve() for key in
             ("initial_state_artifact", "trace_artifact", "upstream_artifact")}
    if any(not p.is_relative_to(root.resolve()) or not p.is_file() for p in paths.values()):
        raise ValueError("Missing or escaping artifact")
    initial = load(paths["initial_state_artifact"])
    if initial["condition"] != condition or not near(initial["mass_readback_kg"], [[condition["object_mass_kg"]]]):
        raise ValueError("Physical mass or condition mismatch")
    payload = load(paths["trace_artifact"].with_name("skill.json"))
    checksum = payload.pop("skill_sha256")
    skill = TemporalSkill.from_dict(payload)
    if checksum != skill.sha256 or checksum != row["skill_sha256"]:
        raise ValueError("Executed skill hash mismatch")
    trace = read_jsonl(paths["trace_artifact"])
    if len(trace) != row["steps"] or not trace:
        raise ValueError("Trace step count mismatch")
    joint_samples, max_delta, max_action = 0, 0., 0.
    limits = initial["joint_limits"][0]
    previous, opened, remaining = None, False, 0
    arm = mapping["arm_action"]
    grip = mapping["gripper_action"]["start"]
    for index, step in enumerate(trace):
        if step["step"] != index:
            raise ValueError("Trace step sequence changed")
        raw, applied = step["raw_action"][0], step["applied_action"][0]
        if len(raw) != len(applied):
            raise ValueError("Action dimensions differ")
        expected = list(raw)
        for i in range(arm["start"], arm["stop"]):
            target = raw[i] * skill.arm_action_gain
            expected[i] = target if previous is None else (
                skill.arm_smoothing_alpha * target + (1 - skill.arm_smoothing_alpha) * previous[i])
        if skill.gripper_hold_steps:
            if remaining > 0:
                expected[grip], remaining = -1., remaining - 1
            elif raw[grip] > 0:
                opened = True
            elif raw[grip] < 0 and opened and index >= 15:
                expected[grip], remaining, opened = -1., skill.gripper_hold_steps - 1, False
        expected = [struct.unpack('f', struct.pack('f', x))[0] for x in expected]
        for a, b in zip(expected, applied, strict=True):
            if not math.isfinite(b) or not math.isclose(a, b, abs_tol=1e-5, rel_tol=1e-5):
                raise ValueError("Executed temporal action disagrees with frozen skill")
        previous = expected
        max_delta = max(max_delta, max(abs(a - b) for a, b in zip(raw, applied, strict=True)))
        max_action = max(max_action, max(abs(b) for b in applied))
        joint_samples += sum(x < low - .001 or x > high + .001
                             for x, (low, high) in zip(step["joint_position"][0], limits, strict=True))
    if joint_samples != row["joint_limit_violation_count"]:
        raise ValueError("Joint-limit counter disagrees with raw states")
    if not math.isclose(max_delta, row["maximum_action_change_abs"], abs_tol=1e-4, rel_tol=1e-5):
        raise ValueError("Action delta counter changed")
    if not math.isclose(max_action, row["maximum_action_abs"], abs_tol=1e-5, rel_tol=1e-5):
        raise ValueError("Action magnitude changed")
    finished = [r for r in read_jsonl(paths["upstream_artifact"]) if r.get("episode_length", 0) > 0]
    if len(finished) != 1 or finished[0]["success"] != row["success"] or finished[0]["episode_length"] != row["steps"]:
        raise ValueError("Official outcome mismatch")
    if load(paths["trace_artifact"].with_name("episode.json")) != row:
        raise ValueError("Per-episode metadata changed")
    return initial
