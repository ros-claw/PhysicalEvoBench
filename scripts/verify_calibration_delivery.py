"""Verify hashes, extract a fresh copy and re-audit every completed physical rollout."""

import argparse
import json
import subprocess
import tarfile
from pathlib import Path

from physicalevobench.calibration.audit import audit_run, lines, load
from physicalevobench.doctor import save_json, sha256


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--evidence',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--skip-private-models',action='store_true')
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    evidence=Path(a.evidence).absolute()
    out=Path(a.output).absolute()
    out.mkdir(parents=True,exist_ok=False)
    sums=(evidence/'SHA256SUMS').read_text().splitlines()
    for line in sums:
        digest,name=line.split('  ',1)
        if sha256(evidence/name)!=digest:
            raise ValueError(f'Published digest mismatch: {name}')
    manifest=load(evidence/'manifest.json')
    runs=out/'runs'
    runs.mkdir()
    for item in manifest['runs']:
        path=evidence/item['archive']
        if sha256(path)!=item['sha256']:
            raise ValueError('Archive manifest differs from actual bytes')
        with tarfile.open(path,'r:gz') as archive:
            archive.extractall(runs,filter='data')
    source_checks=0
    for config in runs.rglob('config.json'):
        cfg=load(config)
        if 'source_commit' not in cfg:
            continue
        source=evidence/f"source-{cfg['source_commit'][:12]}.tar.gz"
        with tarfile.open(source,'r:gz') as archive:
            import hashlib

            for name,digest in cfg['source_sha256'].items():
                actual=hashlib.sha256(archive.extractfile(name).read()).hexdigest()
                if actual!=digest:
                    raise ValueError('Registered source digest differs from archived Git source')
                source_checks+=1
    completed=0
    for index in sorted(runs.rglob('episodes.jsonl')):
        directory=index.parent
        status=load(directory/'status.json')
        if status['status']!='COMPLETED':
            if lines(index):
                raise ValueError('Unexpected partial completed evidence; inspect explicitly')
            continue
        audit=audit_run(directory)
        completed+=audit['physical_episodes']
    for suffix in ('fresh','fresh-frozen'):
        argv=[str(root/'.venv/bin/python'),'-m','physicalevobench.calibration.replay_audit',
              '--persistent',str(runs/'calibration-replay-20261023-001'),
              '--fresh',str(runs/f'calibration-replay-{suffix}-20261023-001')]
        subprocess.run(argv,cwd=root,check=True)
    isolated=runs/'calibration-isolated-confirmation-20261023-001'
    if isolated.exists():
        subprocess.run([str(root/'.venv/bin/python'),'-m','physicalevobench.calibration.isolated_audit',
                        '--run-dir',str(isolated)],cwd=root,stdout=subprocess.DEVNULL,check=True)
    training=runs/'calibration-ppo-train-20261023-002'
    if not a.skip_private_models:
        argv=[str(root/'external/IsaacLab-Arena/.venv/bin/python'),'-m',
              'physicalevobench.calibration.training_audit','--run-dir',str(training)]
        with (out/'training_reaudit_console.json').open('w') as stream:
            subprocess.run(argv,cwd=root,stdout=stream,check=True)
    else:
        for item in load(training/'training_archive.json')['chunks']:
            if sha256(training/item['path'])!=item['sha256']:
                raise ValueError('Training chunk digest mismatch')
    validation=runs/'calibration-ppo-validation-20261023-002'
    heldout=runs/'calibration-ppo-heldout-20261023-001'
    decision=load(validation/'decision.json')
    arms=load(validation/'audit.json')['arms']
    promote=arms['candidate']['successes']>arms['original']['successes'] and arms['candidate']['joint_samples']<=arms['original']['joint_samples']
    if (decision['decision']=='promote')!=promote or decision!=load(heldout/'config.json')['retention_decision']:
        raise ValueError('Validation gate or frozen heldout decision mismatch')
    if decision['frozen_at']>=load(heldout/'config.json')['registered_at']:
        raise ValueError('Heldout registered before retained-policy freeze')
    subprocess.run([str(root/'.venv/bin/python'),str(root/'scripts/summarize_calibration_learning.py'),
                    '--runs-root',str(runs),'--output',str(out/'summary.json')],cwd=root,check=True,
                   stdout=subprocess.DEVNULL)
    summary=load(out/'summary.json')
    expected_completed=422 if isolated.exists() else 326
    if completed!=expected_completed or summary['completed_evaluation_and_diagnostic_episodes']!=completed:
        raise ValueError('Delivery completed physical-episode count mismatch')
    save_json(out/'verification.json',{'status':'PASS','completed_evaluation_and_diagnostic_episodes':completed,
        'training_transitions':summary['training_transitions'],
        'training_model_tensor_reaudit':'NOT_RECHECKED_PRIVATE_WEIGHTS_REQUIRED' if a.skip_private_models else 'PASS',
        'training_transitions_and_official_lengths_reaudit':'HASHES_ONLY' if a.skip_private_models else 'PASS',
        'registered_source_file_checks':source_checks,'published_file_checks':len(sums),
        'heldout_statistics':summary['heldout_statistics'],
        'isolated_confirmation':summary.get('isolated_confirmation'),
        'scope':'delivery integrity and recorded evidence consistency, not hostile-actor security or universal self-evolution'})
    print(json.dumps(load(out/'verification.json'),indent=2))


if __name__=='__main__':
    main()
