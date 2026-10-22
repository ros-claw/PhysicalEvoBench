"""Independent audit of real confirmation traces and preregistered selection gates."""

import argparse
import json
import math
import random
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.audit import near, read_jsonl
from physicalevobench.evaluation.confirmation_stats import ARMS, summarize
from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec


def load(path):
    return json.loads(Path(path).read_text())


def audit_episode(root, row, condition, mapping):
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
    skill = SkillSpec.from_dict(payload)
    if checksum != skill.sha256 or checksum != row["skill_sha256"]:
        raise ValueError("Executed skill hash mismatch")
    trace = read_jsonl(paths["trace_artifact"])
    if len(trace) != row["steps"] or not trace:
        raise ValueError("Trace step count mismatch")
    joint_samples, max_delta, max_action = 0, 0., 0.
    limits = initial["joint_limits"][0]
    for index, step in enumerate(trace):
        if step["step"] != index:
            raise ValueError("Trace step sequence changed")
        raw, applied = step["raw_action"][0], step["applied_action"][0]
        if len(raw) != len(applied):
            raise ValueError("Action dimensions differ")
        for i, (a, b) in enumerate(zip(raw, applied, strict=True)):
            expected = a * skill.arm_action_gain if mapping["start"] <= i < mapping["stop"] else a
            if not math.isfinite(b) or not math.isclose(b, expected, abs_tol=1e-5, rel_tol=1e-5):
                raise ValueError("Executed action disagrees with hashed skill")
            max_delta, max_action = max(max_delta, abs(b - a)), max(max_action, abs(b))
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


def audit_seed(root):
    root = Path(root).absolute()
    config = load(root / "config_resolved.json")
    guarded=config.get("skill_family")=="guarded-1"
    from physicalevobench.protocols.guarded_skill import GuardedSkill

    skill_type=GuardedSkill if guarded else SkillSpec
    freeze_boundary=config["physical_budgets_per_seed"]["train"]+config["physical_budgets_per_seed"]["validation"]
    rows, ledger = read_jsonl(root / "episodes.jsonl"), load(root / "budget_ledger.json")
    if load(root / "status.json")["status"] != "PHYSICAL_COMPLETED":
        raise ValueError("Incomplete physical execution")
    manifests = {s: read_jsonl(root / "splits" / f"{s}.jsonl") for s in config["conditions"]}
    hashes = load(root / "manifest_hashes.json")
    registry = {c["condition_id"]: c for group in manifests.values() for c in group}
    if len(registry) != sum(config["conditions"].values()):
        raise ValueError("Duplicate condition")
    if len({c["seed"] for c in registry.values()}) != len(registry):
        raise ValueError("Split seed overlap")
    for split, count in config["conditions"].items():
        if len(manifests[split]) != count or sha256(root / "splits" / f"{split}.jsonl") != hashes[split]:
            raise ValueError("Manifest mismatch")
    if [r["episode_id"] for r in rows] != [r["episode_id"] for r in ledger] or len(set(r["episode_id"] for r in rows)) != len(rows):
        raise ValueError("Budget ledger mismatch")
    for split, limit in config["physical_budgets_per_seed"].items():
        if [r["used"] for r in ledger if r["split"] == split] != list(range(1, limit + 1)):
            raise ValueError("Physical budget mismatch")
    full_mapping = load(root / "action_mapping.json")
    mapping = full_mapping["arm_action"]
    initial_states = {}
    indexed = {r["episode_id"]: r for r in rows}
    for row in rows:
        if guarded:
            from physicalevobench.evaluation.temporal_audit import audit_temporal_episode

            initial=audit_temporal_episode(root,row,registry[row["condition_id"]],full_mapping)
        else:
            initial = audit_episode(root, row, registry[row["condition_id"]], mapping)
        prior = initial_states.setdefault(row["condition_id"], initial)
        for key in ("joint_position", "object_position", "object_orientation", "target_command", "inertia_readback"):
            if not near(initial[key], prior[key]):
                raise ValueError(f"Paired initial state mismatch: {key}")
    baseline = skill_type.from_dict(load(root / "baseline_skill.json"))
    freeze, event = load(root / "frozen_skills.json"), load(root / "freeze_event.json")
    if freeze["frozen"]["sha256"] != baseline.sha256 or freeze["identity_replay"] != freeze["frozen"]:
        raise ValueError("Identity replay differs from original")
    if not event["proposal_processes_terminated"] or event["episodes_completed"] != freeze_boundary:
        raise ValueError("Invalid freeze boundary")
    checksum = sha256(root / "frozen_skills.json")
    if checksum != event["freeze_sha256"]:
        raise ValueError("Frozen skill manifest changed")
    tests = [r for r in rows if r["split"] == "heldout_test"]
    if any(r["split"] == "heldout_test" for r in rows[:freeze_boundary]) or any(r["split"] != "heldout_test" for r in rows[freeze_boundary:]):
        raise ValueError("Test ran before adaptation finished")
    for reservation in ledger[freeze_boundary:]:
        if reservation["freeze_sha256"] != checksum or reservation["reserved_at"] < event["frozen_at"]:
            raise ValueError("Skill not frozen before test")
    for arm in ARMS:
        group = [r for r in tests if r["agent_id"] == arm]
        if {r["condition_id"] for r in group} != {c["condition_id"] for c in manifests["heldout_test"]} or len(group) != config["conditions"]["heldout_test"]:
            raise ValueError("Test coverage differs")
        skill = skill_type.from_dict(freeze[arm]["skill"])
        if freeze[arm]["sha256"] != skill.sha256 or any(r["skill_sha256"] != skill.sha256 for r in group):
            raise ValueError("Test skill changed")
    # Recompute train selection and validation gate without calling the proposal implementation.
    decisions = load(root / "decisions.json")
    for arm in ("feedback", "random"):
        final_request = load(root / "search" / f"{arm}-3-request.json")
        for trial in range(4):
            request = load(root / "search" / f"{arm}-{trial}-request.json")
            if set(request) != {"agent", "rng_seed", "history", "remaining_budget"} or len(request["history"]) != trial + 1:
                raise ValueError("Invalid updater request")
            response = load(root / "search" / f"{arm}-{trial}-response.json")
            if guarded:
                from physicalevobench.agents.guarded_search_worker import OPTIONS

                expected_name=None
                if trial<3:
                    if arm=="random":
                        expected_name=random.Random(config["seed"] ^ 911).sample(list(OPTIONS),3)[trial]
                    elif trial<2:
                        expected_name=("hold10guard10look2","hold10guard6")[trial]
                    else:
                        scores=[sum(f["success"] for f in h["feedback"]) for h in request["history"]]
                        expected_name="hold10guard2" if scores[1]>=scores[2] else "guard6look2"
                expected_skill=(GuardedSkill(config["checkpoint_sha256"],trial+1,**OPTIONS[expected_name]).to_dict()
                                if expected_name else None)
                if response["next_skill"]!=expected_skill:
                    raise ValueError("Guarded proposal deviated from registered algorithm")
                if trial<3 and final_request["history"][trial+1]["skill"]!=expected_skill:
                    raise ValueError("Executed guarded proposal differs from response")
            else:
                expected_gain = None
                if trial < 3:
                    if arm == "random":
                        expected_gain = random.Random(config["seed"] ^ 911).sample(
                            (.85, .9, .95, 1.05, 1.1, 1.15), 3)[trial]
                    elif trial < 2:
                        expected_gain = (.9, 1.1)[trial]
                    else:
                        scores = [sum(f["success"] for f in h["feedback"]) for h in request["history"]]
                        side = 1 if scores[1] >= scores[2] else 2
                        expected_gain = ((.85 if side == 1 else 1.15) if scores[side] > scores[0]
                                         else (.95 if side == 1 else 1.05))
                if response["next_gain"] != expected_gain:
                    raise ValueError("Proposal deviated from preregistered algorithm")
            if request["rng_seed"] != config["seed"] ^ 911 or request["remaining_budget"] != (3 - trial) * 8:
                raise ValueError("Updater RNG or charged budget changed")
            if not guarded and trial < 3 and final_request["history"][trial + 1]["skill"]["arm_action_gain"] != expected_gain:
                raise ValueError("Executed proposal differs from response")
            for entry in request["history"]:
                if set(entry) != {"skill", "feedback"}:
                    raise ValueError("Updater received hidden fields")
                skill = skill_type.from_dict(entry["skill"])
                if len(entry["feedback"]) != 8:
                    raise ValueError("Train feedback count mismatch")
                for value in entry["feedback"]:
                    f = TrainingFeedback.from_payload(value)
                    actual = indexed[f.episode_id]
                    if actual["split"] != "train" or actual["success"] != f.success or actual["failure_type"] != f.failure_type or actual["skill_sha256"] != skill.sha256:
                        raise ValueError("Updater feedback differs from train evidence")
        history = final_request["history"]
        chosen = sorted(enumerate(history), key=lambda p: (
            -sum(f["success"] for f in p[1]["feedback"]),
            abs(p[1]["skill"]["arm_action_gain"] - 1), p[0]))[0][1]
        selected = skill_type.from_dict(chosen["skill"])
        if selected.to_dict() != decisions[arm]["selected_skill"]:
            raise ValueError("Train-selected skill mismatch")
        old = [r for r in rows if r["split"] == "validation" and r["agent_id"] == "frozen"]
        new = [r for r in rows if r["split"] == "validation" and r["agent_id"] == arm]
        expected_ids = {c["condition_id"] for c in manifests["validation"]}
        if (len(old) != config["conditions"]["validation"] or len(new) != config["conditions"]["validation"] or {r["condition_id"] for r in old} != expected_ids
                or {r["condition_id"] for r in new} != expected_ids
                or any(r["skill_sha256"] != baseline.sha256 for r in old)):
            raise ValueError("Validation coverage or original skill mismatch")
        if any(r["skill_sha256"] != selected.sha256 for r in new):
            raise ValueError("Validation used incorrect selected skill")
        promote = sum(r["success"] for r in new) > sum(r["success"] for r in old) and sum(r["joint_limit_violation_count"] for r in new) <= sum(r["joint_limit_violation_count"] for r in old)
        if decisions[arm]["decision"] != ("promote" if promote else "rollback") or freeze[arm]["sha256"] != (selected.sha256 if promote else baseline.sha256):
            raise ValueError("Promotion gate mismatch")
    return {"status": "PASS", "physical_episodes_verified": len(rows),
            "heldout_conditions": len(manifests["heldout_test"]), "control_traces_verified": True,
            "budget_verified": True, "freeze_verified": True}


def audit_study(directory):
    root = Path(directory).absolute()
    config, prereg = load(root / "study_config.json"), load(root / "preregistration.json")
    if sha256(root / "study_config.json") != prereg["config_sha256"]:
        raise ValueError("Study config changed")
    seed_rows, freezes, ids, seeds, audits = [], [], set(), set(), {}
    old_seeds = set(prereg["prior_episode_seeds_excluded"])
    processes = load(root / "processes.json")
    source_hashes = None
    for seed in config["seeds"]:
        d = root / f"seed-{seed}"
        cfg = load(d / "config_resolved.json")
        if any(cfg[key] != value for key, value in config.items() if key != "arena_path"):
            raise ValueError("Per-seed scientific config changed")
        prov = load(d / "provenance.json")
        if prov["blockers"] or prov["project_commit"] != prereg["project_commit"]:
            raise ValueError("Runtime differs from preregistered commit or doctor failed")
        if source_hashes is None:
            source_hashes = prov["source_sha256"]
        if prov["source_sha256"] != source_hashes:
            raise ValueError("Runtime source differs between seeds")
        if processes[d.name] != 0:
            retry = load(root / "retry-process.json")
            receipt = load(root / "infrastructure-retry.json")
            failed = root / receipt["failed_attempt"]
            if (not failed.is_dir() or not (failed / "console.log").is_file()
                    or retry["seed"] != seed or retry["returncode"] != 0
                    or receipt["completed_episodes_in_failed_attempt"] != 0
                    or (failed / "episodes.jsonl").exists()):
                raise ValueError("Failed execution lacks a valid zero-episode infrastructure retry")
        audits[str(seed)] = audit_seed(d)
        for split in config["conditions"]:
            path = d / "splits" / f"{split}.jsonl"
            if sha256(path) != prereg["manifests"][d.name + "/" + path.name]:
                raise ValueError("Preregistered split changed")
            for condition in read_jsonl(path):
                if condition["seed"] in seeds | old_seeds or condition["condition_id"] in ids:
                    raise ValueError("Cross-study seed or ID overlap")
                seeds.add(condition["seed"])
                ids.add(condition["condition_id"])
        seed_rows.append([r for r in read_jsonl(d / "episodes.jsonl") if r["split"] == "heldout_test"])
        freezes.append(load(d / "frozen_skills.json"))
    metrics = summarize(seed_rows, freezes, config["bootstrap_samples"], config["alpha_familywise"])
    save_json(root / "metrics.json", metrics)
    save_json(root / "audit.json", {"status": "PASS", "seeds": audits,
              "total_physical_episodes": sum(a["physical_episodes_verified"] for a in audits.values()),
              "heldout_conditions": len(config["seeds"])*config["conditions"]["heldout_test"], "cross_seed_isolation": True})
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_study(args.study_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
