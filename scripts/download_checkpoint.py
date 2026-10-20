"""Download upstream weights outside the repository and record immutable provenance."""

import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from physicalevobench.doctor import sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="01277d4f4944174ea7eb4c701d962a078b75c8ce",
                        help="Resolved to an immutable HF commit")
    parser.add_argument("--local-dir", default="~/models/physicalevobench/franka_lift")
    args = parser.parse_args()
    repo = "nvidia/Arena-Franka-Lift-Object-RL-Task"
    revision = HfApi().model_info(repo, revision=args.revision).sha
    destination = Path(args.local_dir).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    if destination.is_relative_to(root):
        parser.error("Weights must be downloaded outside the source repository")
    snapshot_download(repo_id=repo, revision=revision, local_dir=destination)
    files = {str(p.relative_to(destination)): sha256(p)
             for p in destination.rglob("*") if p.is_file() and ".cache" not in p.parts}
    provenance = {"repository": repo, "revision": revision, "files_sha256": files,
                  "license_source": f"https://huggingface.co/{repo}/blob/{revision}/README.md",
                  "redistributed": False}
    (destination / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
