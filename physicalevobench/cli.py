"""One entry point for real execution and evidence collection."""

import argparse
import json
from pathlib import Path

import yaml

from physicalevobench.doctor import diagnose, save_json


def main():
    parser = argparse.ArgumentParser(prog="physicalevobench")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Read-only environment and checkpoint diagnostics")
    doctor.add_argument("--config", default="configs/lift_mass_v0.yaml")
    doctor.add_argument("--output", default="runs/doctor.json")
    smoke = commands.add_parser("smoke", help="Run the pinned official policy runner")
    smoke.add_argument("--config", default="configs/smoke.yaml")
    smoke.add_argument("--gpu", type=int, default=0)
    smoke.add_argument("--run-dir", default="runs/smoke")
    smoke.add_argument("--policy", choices=["zero_action", "rsl_rl"], default="zero_action")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if args.command == "doctor":
        result = diagnose(config)
        save_json(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2 if result["blockers"] else 0
    if args.command == "smoke":
        from physicalevobench.adapters.arena_worker import smoke
        return smoke(config, args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
