"""Launch the pinned upstream runner in a separate OS process and preserve raw evidence."""

import json
import os
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from physicalevobench.doctor import ARENA_COMMIT, command, save_json, sha256


def smoke(config, args):
    arena = Path(config["arena_path"]).resolve()
    run_dir = Path(args.run_dir).resolve()
    # Never overwrite evidence, even when the previous launch failed.
    run_dir.mkdir(parents=True, exist_ok=False)
    revision = command(["git", "rev-parse", "HEAD"], cwd=arena)
    if revision.get("stdout") != ARENA_COMMIT:
        save_json(run_dir / "status.json", {"status": "BLOCKED", "reason": "ARENA_REVISION_MISMATCH"})
        return 2
    python = Path(config.get("arena_python", str(arena / ".venv/bin/python"))).resolve()
    runner = arena / "isaaclab_arena/evaluation/policy_runner.py"
    checkpoint = Path(os.path.expanduser(config["checkpoint_path"])).resolve()
    if args.policy == "rsl_rl" and (
        not checkpoint.is_file() or sha256(checkpoint) != config.get("checkpoint_sha256")
    ):
        save_json(run_dir / "status.json", {"status": "BLOCKED", "reason": "CHECKPOINT_UNVERIFIED"})
        return 2
    launch = [str(python), str(runner), "--headless", "--device", "cuda:0", "--num_envs", "1",
              "--policy_type", args.policy, "--output_base_dir", str(run_dir / "upstream")]
    if args.policy == "zero_action":
        launch += ["--num_steps", str(config.get("num_steps", 20)), "cube_goal_pose"]
    else:
        launch += ["--num_episodes", str(config.get("num_episodes", 1)),
                   "--checkpoint_path", str(checkpoint), "lift_object"]
    evidence = {"command": launch, "cwd": str(arena), "arena_commit": ARENA_COMMIT,
                "physical_gpu": args.gpu, "started_at": datetime.now(timezone.utc).isoformat(),
                "checkpoint_sha256": sha256(checkpoint) if checkpoint.is_file() else None,
                "policy_type": args.policy}
    save_json(run_dir / "launch.json", evidence)
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES=str(args.gpu),
                       OMNI_KIT_ACCEPT_EULA="YES", ACCEPT_EULA="Y",
                       ISAACLAB_ARENA_FORCE_EXIT_ON_COMPLETE="1")
    returncode = None
    error = None
    with (run_dir / "console.log").open("w") as log:
        try:
            process = subprocess.Popen(launch, cwd=arena, env=environment, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                returncode = process.wait(timeout=config.get("timeout_seconds", 900))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                error = "SIMULATION_TIMEOUT"
        except OSError as exc:
            error = str(exc)
            log.write(error + "\n")
    results = list((run_dir / "upstream").rglob("episode_results_rank*.jsonl"))
    # A zero-step smoke or exit code alone cannot pass the physical episode gate.
    episodes = []
    try:
        episodes = [json.loads(line) for path in results for line in path.read_text().splitlines()
                    if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        error = f"CORRUPT_EPISODE_ARTIFACT:{exc}"
    valid_episodes = [row for row in episodes if isinstance(row, dict)
                      and type(row.get("success")) is bool
                      and type(row.get("episode_length")) is int and row["episode_length"] > 0]
    if returncode == 0 and args.policy == "rsl_rl" and len(valid_episodes) < config.get("num_episodes", 1):
        error = "INCOMPLETE_EPISODE_EVIDENCE"
    status = {**evidence, "returncode": returncode, "error": error,
              "status": "PROCESS_COMPLETED" if returncode == 0 and error is None else "INFRA_FAILURE",
              "upstream_episode_record_count": len(episodes),
              "completed_task_episode_count": len(valid_episodes),
              "p0_gate": "PENDING_EPISODE_REVIEW" if returncode == 0 and error is None and valid_episodes
              and args.policy == "rsl_rl" else "NOT_PASSED",
              "completed_at": datetime.now(timezone.utc).isoformat()}
    save_json(run_dir / "status.json", status)
    print(json.dumps(status, indent=2))
    return 0 if returncode == 0 and error is None else 2
