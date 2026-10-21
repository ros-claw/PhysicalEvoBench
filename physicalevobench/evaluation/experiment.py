"""Trusted adaptation experiment; agents see one serialized train-only request."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

from physicalevobench.doctor import command, diagnose, save_json, sha256
from physicalevobench.evaluation.metrics import paired_metrics
from physicalevobench.evaluation.protocol import Budget, build_manifests, promotion_gate
from physicalevobench.protocols.skill import SkillSpec


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def execute(config, output, worker):
    counts = config["conditions"]
    manifests = build_manifests(config["seed"], counts, config["mass_range_kg"])
    low, high = config["mass_range_kg"]
    # Training deliberately covers the pilot-calibrated interval, before looking at any test result.
    for i, condition in enumerate(manifests["train"]):
        condition["object_mass_kg"] = low + (high - low) * i / (counts["train"] - 1)
    for split, conditions in manifests.items():
        write_jsonl(output / "splits" / f"{split}.jsonl", conditions)
    save_json(output / "manifest_hashes.json", {
        split: sha256(output / "splits" / f"{split}.jsonl") for split in manifests
    })
    budgets = {split: Budget(limit) for split, limit in config["budgets"].items()}
    ledger = []

    def rollouts(split, skill, agent, prefix, relative):
        rows = []
        for i, condition in enumerate(manifests[split]):
            budgets[split].reserve()
            episode_id = f"{prefix}-{i:04d}"
            ledger.append({"episode_id": episode_id, "split": split,
                           "used": budgets[split].used, "limit": budgets[split].limit})
            save_json(output / "budget_ledger.json", ledger)
            row = worker.run_episode(condition, skill, agent, episode_id)
            rows.append(row)
            write_jsonl(output / relative, rows)
        return rows

    current = SkillSpec(worker.checkpoint_hash)
    save_json(output / "baseline/skill_v0.json", current.to_dict())
    training = rollouts("train", current, "frozen", "train-v0", "evolution/training_episodes.jsonl")
    payload = {"skill": current.to_dict(), "remaining_budget": budgets["train"].limit - budgets["train"].used,
               "training_feedback": [{"episode_id": row["episode_id"], "success": row["success"],
                                      "failure_type": row["failure_type"], "split": "train"}
                                     for row in training]}
    save_json(output / "evolution/agent_request.json", payload)
    result = subprocess.run([sys.executable, "-m", "physicalevobench.agents.worker"],
                            input=json.dumps(payload, allow_nan=False), text=True,
                            capture_output=True, timeout=30, check=True)
    response = json.loads(result.stdout)
    save_json(output / "evolution/agent_response.json", response)
    proposal = response["proposal"]
    final = current
    candidate = None
    decision = {"decision": "no_update", "reason": "No permitted training failure or budget"}
    if proposal is not None:
        candidate = SkillSpec.from_dict(proposal["skill"])
        if candidate.sha256 != proposal["skill_sha256"] or candidate.base_checkpoint_sha256 != current.base_checkpoint_sha256:
            raise ValueError("Invalid candidate snapshot")
        failures = {row["episode_id"] for row in training if not row["success"]}
        if not proposal["source_episode_ids"] or not set(proposal["source_episode_ids"]) <= failures:
            raise ValueError("Proposal must reference actual training failures")
        write_jsonl(output / "evolution/proposals.jsonl", [proposal])
        save_json(output / "evolution/candidate_skill_v1.json", candidate.to_dict())
        candidate_training = rollouts("train", candidate, "feedback_search", "train-candidate",
                                      "evolution/candidate_training_episodes.jsonl")
        training += candidate_training
        write_jsonl(output / "evolution/training_episodes.jsonl", training)
        incumbent = rollouts("validation", current, "frozen", "validation-v0",
                             "evolution/incumbent_validation_episodes.jsonl")
        challenger = rollouts("validation", candidate, "feedback_search", "validation-candidate",
                              "evolution/candidate_validation_episodes.jsonl")
        decision = promotion_gate(incumbent, challenger, config["promotion_min_gain"])
        old_violations = sum(row["joint_limit_violation_count"] for row in incumbent)
        new_violations = sum(row["joint_limit_violation_count"] for row in challenger)
        decision.update(incumbent_joint_limit_samples=old_violations,
                        candidate_joint_limit_samples=new_violations)
        if config["require_no_increase_joint_limit_samples"] and new_violations > old_violations:
            decision.update(decision="rollback", reason="Joint-limit sample count increased")
        if not any(row["maximum_action_change_abs"] > 0 for row in candidate_training):
            raise ValueError("Candidate did not change any executed control action")
        if decision["decision"] == "promote":
            final = candidate
    write_jsonl(output / "evolution/promotion_decisions.jsonl", [decision])
    save_json(output / "evolution/skill_diff.json", {"before": current.to_dict(),
              "candidate": candidate.to_dict() if candidate else None, "retained": final.to_dict(),
              "decision": decision})
    save_json(output / "evolution/final_skill.json", final.to_dict())
    save_json(output / "frozen_skills.json", {"baseline_sha256": current.sha256,
              "updated_sha256": final.sha256, "updater_process_terminated": True,
              "frozen_before_test": True})
    frozen = rollouts("heldout_test", current, "frozen", "test-frozen", "test/baseline_episodes.jsonl")
    updated = rollouts("heldout_test", final, "feedback_search", "test-updated", "test/updated_episodes.jsonl")
    if final.sha256 != SkillSpec.from_dict(json.loads((output / "evolution/final_skill.json").read_text())).sha256:
        raise ValueError("Frozen skill changed during test")
    metrics = paired_metrics(frozen, updated, bootstrap_seed=config["seed"])
    metrics.update(training_episode_budget_used=budgets["train"].used,
                   validation_episode_budget_used=budgets["validation"].used,
                   test_episode_budget_used=budgets["heldout_test"].used,
                   candidate_count=int(candidate is not None),
                   promotion_count=int(decision["decision"] == "promote"),
                   fallback_count=int(decision["decision"] == "rollback"), model_token_usage=0,
                   learned_skill_sha256=final.sha256, decision=decision)
    save_json(output / "report/metrics.json", metrics)
    save_json(output / "status.json", {"status": "PHYSICAL_EXPERIMENT_COMPLETED",
              "candidate_executed": candidate is not None, "physical_mvp_accepted": False})
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if config.get("distribution_frozen") is not True or config["conditions"]["heldout_test"] < 16:
        raise ValueError("Freeze calibrated distribution and at least 16 heldout pairs before running")
    if config["conditions"]["train"] < 2:
        raise ValueError("Training requires at least two conditions")
    output = Path(args.run_dir).absolute()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "run.lock").open("x"):
        pass  # No unsafe resume, even after an infrastructure failure.
    save_json(output / "config_resolved.json", config)
    provenance = diagnose(config)
    project_root = Path(__file__).resolve().parents[2]
    provenance["project_commit"] = command(["git", "rev-parse", "HEAD"], cwd=project_root)
    provenance["project_worktree"] = command(["git", "status", "--porcelain"], cwd=project_root)
    provenance["source_sha256"] = {str(path.relative_to(project_root)): sha256(path)
                                  for path in (project_root / "physicalevobench").rglob("*.py")}
    save_json(output / "provenance.json", provenance)
    if provenance["blockers"]:
        raise RuntimeError(provenance["blockers"])
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app_args = get_isaaclab_arena_cli_parser().parse_args(["--device", "cuda:0"])
    with SimulationAppContext(app_args):
        from physicalevobench.adapters.lift_worker import LiftWorker

        worker = LiftWorker(Path(config["checkpoint_path"]).expanduser(), output)
        try:
            execute(config, output, worker)
        except Exception as error:
            save_json(output / "status.json", {"status": "INFRA_FAILURE", "error": str(error)})
            raise
        finally:
            worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
