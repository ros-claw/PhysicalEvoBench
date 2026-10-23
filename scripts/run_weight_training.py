"""Freeze the training recipe and launch the trusted collector."""

import argparse
import subprocess
from pathlib import Path

import yaml

from physicalevobench.adapters.arena_worker import arena_python_path, runtime_environment
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--candidate',required=True)
    p.add_argument('--gpu',type=int,default=2)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit source before training')
    cfg = yaml.safe_load((root/'configs/confirmation.yaml').read_text())
    cfg.update(schema_version='weight-training-1', num_envs=128, iterations=200,
               learner_seed=2026102301, environment_seed=202610230301, transition_budget=614400,
               candidate_path=str(Path(a.candidate).expanduser().absolute()),
               registered_at=now(), source_commit=command(['git','rev-parse','HEAD'],cwd=root)['stdout'],
               source_sha256={str(f.relative_to(root)):sha256(f) for f in (root/'physicalevobench').rglob('*.py')})
    if Path(cfg['candidate_path']).exists():
        raise ValueError('Refuse to overwrite existing checkpoint')
    out = Path(a.output).absolute()
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'config.json',cfg)
    arena = (root/cfg['arena_path']).resolve()
    argv = [str(arena_python_path(cfg,arena)),'-m','physicalevobench.calibration.train','--run-dir',str(out)]
    save_json(out/'launch.json',{'argv':argv,'gpu':a.gpu})
    with (out/'console.log').open('w') as log:
        result = subprocess.run(argv,cwd=arena,env=runtime_environment(arena,a.gpu),stdout=log,
                                stderr=subprocess.STDOUT,timeout=7200)
    save_json(out/'process.json',{'returncode':result.returncode,'finished_at':now()})
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
