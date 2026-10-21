"""Continue a slow pinned installation into real official P0 rollouts, without a chat session."""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-pid", type=int, default=None)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    arena = root / "external/IsaacLab-Arena"
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    lock = (root / "runs/p0-bootstrap.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    environment = dict(os.environ, UV_CACHE_DIR=str(root / ".cache/uv"),
                       TMPDIR=str(root / ".cache/tmp"), PYTHONPATH=str(root),
                       OMNI_KIT_ACCEPT_EULA="YES", ACCEPT_EULA="Y")
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    state = {"schema_version": "0.1", "status": "WAITING_FOR_INSTALL", "steps": [],
             "physical_mvp_accepted": False, "started_at": datetime.now(timezone.utc).isoformat()}

    def save():
        temporary = run_dir / "status.tmp"
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        temporary.replace(run_dir / "status.json")

    def run_step(name, command, cwd, timeout):
        state["status"] = name
        entry = {"name": name, "command": list(map(str, command)), "cwd": str(cwd),
                 "started_at": datetime.now(timezone.utc).isoformat(), "returncode": None}
        state["steps"].append(entry)
        save()
        with (run_dir / f"{name.lower()}.log").open("w") as log:
            try:
                result = subprocess.run(entry["command"], cwd=cwd, env=environment,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                entry["returncode"] = result.returncode
            except (OSError, subprocess.TimeoutExpired) as error:
                entry["error"] = str(error)
                log.write(str(error) + "\n")
        entry["completed_at"] = datetime.now(timezone.utc).isoformat()
        if entry["returncode"] != 0:
            state["status"] = "BLOCKED"
            save()
            return False
        save()
        return True

    save()
    if args.wait_pid is not None:
        # Match process start time as well as PID to avoid following a reused PID.
        process_stat = Path(f"/proc/{args.wait_pid}/stat")
        try:
            start = process_stat.read_text().split()[21]
            while process_stat.exists():
                try:
                    if process_stat.read_text().split()[21] != start:
                        break
                except FileNotFoundError:
                    break
                time.sleep(10)
        except FileNotFoundError:
            pass
    steps = [
        ("PINNED_INSTALL", ["uv", "sync", "--locked", "--extra", "dev"], arena, 21600),
        ("NATIVE_DOCTOR", [arena / ".venv/bin/python", "-m", "physicalevobench.cli", "doctor",
                           "--config", root / "configs/lift_mass_v0.yaml", "--output",
                           run_dir / "doctor.json"], root, 120),
    ]
    for name, command, cwd, timeout in steps:
        if not run_step(name, command, cwd, timeout):
            return 2
    for policy in ("zero_action", "rsl_rl"):
        command = [sys.executable, "-m", "physicalevobench.cli", "smoke", "--config",
                   root / "configs/smoke.yaml", "--gpu", str(args.gpu), "--policy", policy,
                   "--run-dir", run_dir / policy]
        if not run_step(policy.upper(), command, root, 1020):
            return 2
    state["status"] = "OFFICIAL_ROLLOUTS_COMPLETED_REVIEW_REQUIRED"
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
