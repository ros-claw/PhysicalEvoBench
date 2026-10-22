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


def prepare(config, output, gpus):
    if config["schema_version"] != "confirmation-1" or len(config["seeds"]) != 3:
        raise ValueError("Expected fixed three-seed confirmation protocol")
    if config["conditions"] != {"train": 8, "validation": 8, "heldout_test": 24}:
        raise ValueError("Confirmation conditions differ from preregistration")
    if config["physical_budgets_per_seed"] != {"train": 56, "validation": 24, "heldout_test": 96}:
        raise ValueError("Incorrect fixed budgets")
    if config["gain_grid"] != [.85, .9, .95, 1.05, 1.1, 1.15]:
        raise ValueError("Unregistered gain grid")
    root = Path(__file__).resolve().parents[1]
    if command(["git", "status", "--porcelain"], cwd=root)["stdout"]:
        raise ValueError("Commit preregistration and implementation before launch")
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "study_config.json", config)
    old_seeds = {42, 1000, 1001}
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
        "protocol_sha256": sha256(root / "docs/experiments/CONFIRMATION_PREREGISTRATION.md"),
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
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    output = Path(args.output).absolute()
    directories = prepare(config, output, args.gpus)
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
