"""Freeze three prospective manifests, then supervise independent real GPU executions."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.protocol import build_manifests
from physicalevobench.evaluation.seed_registry import published_seeds


def prepare(config, output, gpus, development_gate=None):
    guarded=config["schema_version"] == "guarded-confirmation-1"
    if len(config["seeds"])!=3 or config["schema_version"] not in {"confirmation-1","guarded-confirmation-1"}:
        raise ValueError("Expected registered three-seed protocol")
    expected_counts={"train":8,"validation":16 if guarded else 8,"heldout_test":32 if guarded else 24}
    expected_budgets={"train":56,"validation":48 if guarded else 24,"heldout_test":128 if guarded else 96}
    if config["conditions"]!=expected_counts or config["physical_budgets_per_seed"]!=expected_budgets:
        raise ValueError("Conditions or budgets differ from registration")
    if guarded:
        if development_gate is None:
            raise ValueError("Guarded confirmation requires a promoted development gate")
        gate=Path(development_gate)
        decision=json.loads((gate/"decision.json").read_text())
        if decision["decision"]!="promote" or json.loads((gate/"audit.json").read_text())["status"]!="PASS":
            raise ValueError("Development gate did not promote an independently audited update")
        config=dict(config,development_gate_sha256=sha256(gate/"decision.json"))
    elif config["gain_grid"] != [.85,.9,.95,1.05,1.1,1.15]:
        raise ValueError("Unregistered gain grid")
    root = Path(__file__).resolve().parents[1]
    if command(["git", "status", "--porcelain"], cwd=root)["stdout"]:
        raise ValueError("Commit preregistration and implementation before launch")
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "study_config.json", config)
    old_seeds = published_seeds(root) if guarded else {42, 1000, 1001}
    for p in (root / "docs/evidence").rglob("initial_state.json"):
        old_seeds.add(json.loads(p.read_text())["condition"]["seed"])
    all_ids, all_seeds, directories = set(), set(old_seeds), []
    for index, seed in enumerate(config["seeds"]):
        directory = output / f"seed-{seed}"
        directory.mkdir()
        cfg = dict(config, seed=seed, physical_gpu=gpus[index % len(gpus)])
        save_json(directory / "config_resolved.json", cfg)
        manifests = build_manifests(seed, cfg["conditions"], cfg["mass_range_kg"])
        hashes = {}
        for split, conditions in manifests.items():
            for i, c in enumerate(conditions):
                c["condition_id"] = f"s{seed}-{c['condition_id']}"
                if c["seed"] in all_seeds or c["condition_id"] in all_ids:
                    raise ValueError("Seed or condition reuse")
                all_seeds.add(c["seed"])
                all_ids.add(c["condition_id"])
                if split == "train":
                    low, high = cfg["mass_range_kg"]
                    c["object_mass_kg"] = low + (high - low) * i / (len(conditions) - 1)
            path = directory / "splits" / f"{split}.jsonl"
            path.parent.mkdir(exist_ok=True)
            path.write_text("".join(json.dumps(c) + "\n" for c in conditions))
            hashes[split] = sha256(path)
        save_json(directory / "manifest_hashes.json", hashes)
        directories.append(directory)
    save_json(output / "preregistration.json", {
        "frozen_at": now(), "project_commit": command(["git", "rev-parse", "HEAD"], cwd=root),
        "protocol_sha256": sha256(root / ("docs/experiments/GUARDED_CONFIRMATION_PREREGISTRATION.md" if guarded else "docs/experiments/CONFIRMATION_PREREGISTRATION.md")),
        "config_sha256": sha256(output / "study_config.json"),
        "prior_episode_seeds_excluded": sorted(old_seeds),
        "manifests": {p.parent.parent.name + "/" + p.name: sha256(p)
                      for d in directories for p in (d / "splits").glob("*.jsonl")}})
    return directories


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/confirmation.yaml")
    parser.add_argument("--output", required=True)
    parser.add_argument("--gpus", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--development-gate")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    output = Path(args.output).absolute()
    directories = prepare(config, output, args.gpus, args.development_gate)
    arena = Path(config["arena_path"]).resolve()
    processes = []
    for index, directory in enumerate(directories):
        gpu = args.gpus[index % len(args.gpus)]
        launch = [str(arena_python_path(config, arena)), "-m", "physicalevobench.evaluation.confirmation",
                  "--run-dir", str(directory)]
        save_json(directory / "launch.json", {"command": launch, "physical_gpu": gpu})
        log = (directory / "console.log").open("w")
        process = subprocess.Popen(launch, env=runtime_environment(arena, gpu),
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append((directory, process, log, time.monotonic()))
    while any(p.poll() is None for _, p, _, _ in processes):
        for directory, process, log, started in processes:
            if process.poll() is None and time.monotonic() - started > config["timeout_seconds"]:
                import os
                import signal

                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                save_json(directory / "timeout.json", {"timeout_seconds": config["timeout_seconds"]})
        time.sleep(5)
    codes = {}
    for directory, process, log, _ in processes:
        log.close()
        codes[directory.name] = process.wait()
    save_json(output / "processes.json", codes)
    return 0 if all(code == 0 for code in codes.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
