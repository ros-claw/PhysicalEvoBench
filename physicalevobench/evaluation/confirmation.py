"""One prospective seed of the confirmation study, with a real persistent LiftWorker."""

import argparse
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from physicalevobench.doctor import command, diagnose, save_json, sha256
from physicalevobench.evaluation.experiment import write_jsonl
from physicalevobench.protocols.skill import SkillSpec


def now():
    return datetime.now(timezone.utc).isoformat()


def execute(config, output, worker):
    manifests = {split: [json.loads(line) for line in (output / "splits" / f"{split}.jsonl").read_text().splitlines()]
                 for split in config["conditions"]}
    rng = random.Random(config["seed"] ^ 87193)
    ledger, rows = [], []
    used = dict.fromkeys(config["physical_budgets_per_seed"], 0)
    baseline = SkillSpec(worker.checkpoint_hash)
    save_json(output / "baseline_skill.json", baseline.to_dict())

    def episode(split, skill, arm, condition, label):
        used[split] += 1
        if used[split] > config["physical_budgets_per_seed"][split]:
            raise RuntimeError("Reserved physical budget exceeded")
        eid = f"{label}-{condition['condition_id']}"
        ledger.append({"episode_id": eid, "split": split, "agent": arm,
                       "used": used[split], "reserved_at": now(),
                       "freeze_sha256": sha256(output / "frozen_skills.json")
                       if split == "heldout_test" else None})
        save_json(output / "budget_ledger.json", ledger)
        row = worker.run_episode(condition, skill, arm, eid)
        rows.append(row)
        write_jsonl(output / "episodes.jsonl", rows)
        return row

    def history_entry(skill, results):
        return {"skill": skill.to_dict(), "feedback": [
            {"episode_id": r["episode_id"], "success": r["success"],
             "failure_type": r["failure_type"], "split": "train"} for r in results]}

    baseline_train = [episode("train", baseline, "frozen", c, "train-original") for c in manifests["train"]]
    history = {arm: [history_entry(baseline, baseline_train)] for arm in ("feedback", "random")}
    skills = {arm: [baseline] for arm in history}
    selected = {}
    for trial in range(4):
        jobs = {}
        for arm in history:
            payload = {"agent": arm, "rng_seed": config["seed"] ^ 911,
                       "history": history[arm], "remaining_budget": (3 - trial) * len(baseline_train)}
            save_json(output / "search" / f"{arm}-{trial}-request.json", payload)
            child = subprocess.run([sys.executable, "-m", "physicalevobench.agents.search_worker"],
                                   input=json.dumps(payload), capture_output=True, text=True,
                                   timeout=30, check=True)
            response = json.loads(child.stdout)
            save_json(output / "search" / f"{arm}-{trial}-response.json", response)
            if trial == 3:
                if response["next_gain"] is not None:
                    raise RuntimeError("Candidate count exceeded")
                selected[arm] = skills[arm][response["selected_index"]]
            else:
                gain = response["next_gain"]
                if gain not in config["gain_grid"]:
                    raise RuntimeError("Unregistered gain")
                jobs[arm] = SkillSpec(worker.checkpoint_hash, trial + 1, gain)
        if trial == 3:
            break
        results = {arm: [] for arm in jobs}
        for condition in manifests["train"]:
            order = list(jobs)
            rng.shuffle(order)
            for arm in order:
                results[arm].append(episode("train", jobs[arm], arm, condition, f"train-{arm}-{trial}"))
        for arm in jobs:
            skills[arm].append(jobs[arm])
            history[arm].append(history_entry(jobs[arm], results[arm]))
    validation = {arm: [] for arm in ("frozen", "feedback", "random")}
    for condition in manifests["validation"]:
        order = list(validation)
        rng.shuffle(order)
        for arm in order:
            validation[arm].append(episode("validation", baseline if arm == "frozen" else selected[arm],
                                           arm, condition, f"validation-{arm}"))
    decisions = {}
    final = {"frozen": baseline, "identity_replay": baseline}
    for arm in selected:
        original_successes = sum(r["success"] for r in validation["frozen"])
        candidate_successes = sum(r["success"] for r in validation[arm])
        old_joint = sum(r["joint_limit_violation_count"] for r in validation["frozen"])
        new_joint = sum(r["joint_limit_violation_count"] for r in validation[arm])
        promote = candidate_successes > original_successes and new_joint <= old_joint
        final[arm] = selected[arm] if promote else baseline
        decisions[arm] = {"decision": "promote" if promote else "rollback",
                          "selected_skill": selected[arm].to_dict(),
                          "baseline_successes": original_successes,
                          "candidate_successes": candidate_successes,
                          "baseline_joint_samples": old_joint, "candidate_joint_samples": new_joint}
    save_json(output / "decisions.json", decisions)
    frozen = {arm: {"skill": skill.to_dict(), "sha256": skill.sha256} for arm, skill in final.items()}
    save_json(output / "frozen_skills.json", frozen)
    save_json(output / "freeze_event.json", {"frozen_at": now(), "episodes_completed": len(rows),
              "proposal_processes_terminated": True, "freeze_sha256": sha256(output / "frozen_skills.json")})
    # Randomized cyclic order balances all four arms in each four-condition block.
    for i, condition in enumerate(manifests["heldout_test"]):
        if i % 4 == 0:
            order = list(final)
            rng.shuffle(order)
        rotated = order[i % 4:] + order[:i % 4]
        for arm in rotated:
            episode("heldout_test", final[arm], arm, condition, f"test-{arm}")
    if used != config["physical_budgets_per_seed"]:
        raise RuntimeError("Incomplete physical budget")
    save_json(output / "status.json", {"status": "PHYSICAL_COMPLETED", "episodes": len(rows),
              "used_physical_budget": used, "completed_at": now(),
              "charged_per_search": {"train": 32, "validation": 16, "test": 24}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    output = Path(args.run_dir).absolute()
    with (output / "run.lock").open("x"):
        pass
    config = json.loads((output / "config_resolved.json").read_text())
    provenance = diagnose(config)
    root = Path(__file__).resolve().parents[2]
    provenance.update(project_commit=command(["git", "rev-parse", "HEAD"], cwd=root),
                      project_worktree=command(["git", "status", "--porcelain"], cwd=root),
                      started_at=now(), command=[sys.executable, *sys.argv],
                      source_sha256={str(p.relative_to(root)): sha256(p)
                                     for p in (root / "physicalevobench").rglob("*.py")})
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
