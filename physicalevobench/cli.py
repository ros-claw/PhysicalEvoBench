"""One entry point for real execution and evidence collection."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from physicalevobench.doctor import diagnose, save_json


def main():
    parser = argparse.ArgumentParser(prog="physicalevobench")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Read-only environment and checkpoint diagnostics")
    doctor.add_argument("--config", default="configs/lift_mass_v0.yaml")
    doctor.add_argument("--output", default="runs/doctor.json")
    doctor.add_argument("--current-interpreter", action="store_true",
                        help="Inspect this Python instead of auto-selecting an installed Arena runtime")
    smoke = commands.add_parser("smoke", help="Run the pinned official policy runner")
    smoke.add_argument("--config", default="configs/smoke.yaml")
    smoke.add_argument("--gpu", type=int, default=0)
    smoke.add_argument("--run-dir", default="runs/smoke")
    smoke.add_argument("--policy", choices=["zero_action", "rsl_rl"], default="zero_action")
    run = commands.add_parser("run", help="Real physical train/validation/frozen heldout experiment")
    run.add_argument("--config", default="configs/mvp.yaml")
    run.add_argument("--gpu", type=int, default=0)
    run.add_argument("--run-dir", required=True)
    run.add_argument("--agents", default="frozen,feedback_search")
    run.add_argument("--resume", action="store_true")
    for name in ("audit", "report"):
        command = commands.add_parser(name)
        command.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    if args.command == "audit":
        from physicalevobench.evaluation.audit import audit_run
        result = audit_run(args.run_dir)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "PASS" else 2
    if args.command == "report":
        from physicalevobench.reporting.generate import generate_report
        print(generate_report(args.run_dir))
        return 0
    config = yaml.safe_load(Path(args.config).read_text())
    if args.command == "doctor":
        from physicalevobench.adapters.arena_worker import arena_python_path

        arena = Path(config["arena_path"]).absolute()
        runtime = arena_python_path(config, arena)
        if (not args.current_interpreter and runtime.is_file()
                and Path(sys.prefix).resolve() != runtime.parent.parent.resolve()):
            launch = [str(runtime), "-m", "physicalevobench.cli", "doctor", "--current-interpreter",
                      "--config", str(Path(args.config).absolute()), "--output", args.output]
            environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            return subprocess.run(launch, env=environment, check=False).returncode
        result = diagnose(config)
        save_json(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2 if result["blockers"] else 0
    if args.command == "smoke":
        from physicalevobench.adapters.arena_worker import smoke
        return smoke(config, args)
    if args.command == "run":
        from physicalevobench.adapters.arena_worker import run_benchmark
        return run_benchmark(config, args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
