"""Real mass sensitivity pilot; its outcomes must never be reused as heldout results."""

import argparse
import json
import os
import sys
from pathlib import Path

from physicalevobench.doctor import diagnose, save_json, sha256
from physicalevobench.protocols.skill import SkillSpec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--masses", type=float, nargs="+", default=[0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2])
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--seeds", type=int, nargs="+", default=None,
                        help="Paired seeds: replay each seed for every pilot mass")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = Path(args.run_dir).absolute()
    output.mkdir(parents=True, exist_ok=False)
    checkpoint = Path(args.checkpoint).expanduser().absolute()
    config = {"arena_path": str(root / "external/IsaacLab-Arena"),
              "checkpoint_path": str(checkpoint),
              "checkpoint_sha256": "babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa"}
    provenance = diagnose(config)
    provenance["command"] = [sys.executable, *sys.argv]
    save_json(output / "provenance.json", provenance)
    if provenance["blockers"]:
        raise RuntimeError(provenance["blockers"])
    seeds = args.seeds if args.seeds is not None else [args.seed]
    conditions = [{"condition_id": f"pilot-m{i:03d}-s{j:03d}", "split": "pilot", "seed": seed,
                   "object_mass_kg": mass} for i, mass in enumerate(args.masses)
                  for j, seed in enumerate(seeds)]
    save_json(output / "pilot_manifest.json", conditions)
    os.environ["HEADLESS"] = "1"
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app_args = get_isaaclab_arena_cli_parser().parse_args(["--device", "cuda:0"])
    with SimulationAppContext(app_args):
        from physicalevobench.adapters.lift_worker import LiftWorker

        worker = LiftWorker(checkpoint, output)
        try:
            skill = SkillSpec(sha256(checkpoint))
            with (output / "episodes.jsonl").open("w") as log:
                for condition in conditions:
                    row = worker.run_episode(condition, skill, "frozen", condition["condition_id"])
                    log.write(json.dumps(row, allow_nan=False) + "\n")
                    log.flush()
            save_json(output / "status.json", {"status": "PILOT_COMPLETED",
                                               "formal_distribution_frozen": False})
        except Exception as error:
            save_json(output / "status.json", {"status": "INFRA_FAILURE", "error": str(error)})
            raise
        finally:
            worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
