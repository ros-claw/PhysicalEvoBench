"""Read-only host and dependency diagnostics; never imports simulation before AppLauncher."""

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ARENA_COMMIT = "c7edf3a9d5d8276565208f72422f8f8a0806d6cf"


def command(args, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
        return {"command": list(map(str, args)), "returncode": result.returncode,
                "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": list(map(str, args)), "returncode": None, "error": str(error)}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def diagnose(config):
    arena = Path(config["arena_path"]).resolve()
    gpu = command(["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total,memory.free",
                   "--format=csv,noheader"])
    packages = {}
    for name in ["isaacsim", "isaaclab", "isaaclab-arena", "torch", "rsl-rl-lib"]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    revision = command(["git", "rev-parse", "HEAD"], cwd=arena) if arena.exists() else None
    checkpoint = Path(os.path.expandvars(os.path.expanduser(config["checkpoint_path"])))
    checkpoint_hash = sha256(checkpoint) if checkpoint.is_file() else None
    blockers = []
    if gpu["returncode"] != 0:
        blockers.append("NVIDIA_GPU_UNAVAILABLE")
    if not revision or revision.get("stdout") != ARENA_COMMIT:
        blockers.append("ARENA_REVISION_MISMATCH")
    for name in ["isaacsim", "isaaclab", "isaaclab-arena"]:
        if packages[name] is None:
            blockers.append(f"MISSING_PACKAGE:{name}")
    expected_packages = {"isaacsim": "6.1.0.0", "isaaclab": "17.0.2",
                         "isaaclab-arena": "0.3.0", "torch": "2.11.0+cu128",
                         "rsl-rl-lib": "5.4.1"}
    for name, expected in expected_packages.items():
        if packages[name] is None and name not in ("isaacsim", "isaaclab", "isaaclab-arena"):
            blockers.append(f"MISSING_PACKAGE:{name}")
        elif packages[name] is not None and packages[name] != expected:
            blockers.append(f"PACKAGE_VERSION_MISMATCH:{name}:{expected}")
    if not checkpoint.is_file():
        blockers.append("CHECKPOINT_MISSING")
    elif config.get("checkpoint_sha256") != checkpoint_hash:
        blockers.append("CHECKPOINT_HASH_MISMATCH_OR_UNPINNED")
    submodules = command(["git", "submodule", "status", "--recursive"], cwd=arena) if revision else None
    if submodules and (submodules.get("returncode") != 0 or any(
        line.startswith(("-", "+", "U")) for line in submodules.get("stdout", "").splitlines()
    )):
        blockers.append("SUBMODULES_NOT_READY")
    return {
        "schema_version": "0.1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "gpu": gpu, "packages": packages, "arena_revision": revision,
        "expected_packages_from_arena_lock": expected_packages,
        "arena_expected_commit": ARENA_COMMIT,
        "arena_submodules": submodules,
        "disk_free_bytes": shutil.disk_usage(Path.cwd()).free,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_hash,
        "blockers": blockers, "status": "BLOCKED" if blockers else "READY_FOR_SMOKE",
        "physical_episode_executed": False,
    }


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
