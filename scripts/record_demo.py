"""Replay an observed train failure with baseline and rejected candidate; no scores are reused."""

import argparse
import json
import os
from pathlib import Path

from physicalevobench.doctor import save_json
from physicalevobench.evaluation.audit import read_jsonl
from physicalevobench.protocols.skill import SkillSpec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    source = Path(args.experiment).absolute()
    output = Path(args.run_dir).absolute()
    output.mkdir(parents=True, exist_ok=False)
    training = read_jsonl(source / "evolution/training_episodes.jsonl")
    failure = next(row for row in training if row["agent_id"] == "frozen" and not row["success"])
    state = json.loads((source / failure["initial_state_artifact"]).read_text())
    condition = dict(state["condition"], split="demo", condition_id="demo-train-failure-replay")
    config = json.loads((source / "config_resolved.json").read_text())
    baseline = SkillSpec.from_dict(json.loads((source / "baseline/skill_v0.json").read_text()))
    candidate = SkillSpec.from_dict(json.loads((source / "evolution/candidate_skill_v1.json").read_text()))
    save_json(output / "demo_provenance.json", {
        "source_experiment": str(source), "source_episode_id": failure["episode_id"],
        "purpose": "Separate video-only replay; excluded from experimental scores and updater input",
        "candidate_status": "See original validation gate; do not infer promotion from demo",
        "extra_physical_episode_budget": 2,
    })
    os.environ["HEADLESS"] = "1"
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app_args = get_isaaclab_arena_cli_parser().parse_args(["--device", "cuda:0", "--enable_cameras"])
    with SimulationAppContext(app_args):
        from physicalevobench.adapters.lift_worker import LiftWorker

        worker = LiftWorker(Path(config["checkpoint_path"]).expanduser(), output, record_camera_video=True)
        try:
            rows = [worker.run_episode(condition, baseline, "frozen", "baseline-video"),
                    worker.run_episode(condition, candidate, "candidate_replay", "candidate-video")]
            save_json(output / "demo_episodes.json", rows)
        finally:
            worker.close()


if __name__ == "__main__":
    main()
