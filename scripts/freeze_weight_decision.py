"""Prospectively specified strict validation gate, before independent heldout physics."""

import argparse
from pathlib import Path

from physicalevobench.calibration.audit import audit_run, load
from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.confirmation import now


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--validation',required=True)
    p.add_argument('--training',required=True)
    a=p.parse_args()
    run=Path(a.validation).absolute()
    cfg=load(run/'config.json')
    training=Path(a.training).absolute()
    freeze=load(training/'freeze.json')
    if not all(j['condition']['split']=='validation' for j in cfg['jobs']):
        raise ValueError('Must gate on validation only')
    candidate=Path(cfg['additional_checkpoints']['candidate'])
    if sha256(candidate)!=freeze['candidate_sha256'] or not freeze['weight_change']['actor_changed']:
        raise ValueError('Candidate does not match genuinely changed training freeze')
    audit=audit_run(run)
    original,new=audit['arms']['original'],audit['arms']['candidate']
    promote=new['successes']>original['successes'] and new['joint_samples']<=original['joint_samples']
    retained=candidate if promote else Path(cfg['checkpoint_path']).expanduser()
    save_json(run/'decision.json',{'decision':'promote' if promote else 'rollback',
              'original':original,'candidate':new,'retained_checkpoint':str(retained),
              'retained_checkpoint_sha256':sha256(retained),'frozen_at':now(),
              'training_freeze_sha256':sha256(training/'freeze.json'),
              'scope':'validation decision; heldout efficacy not yet measured'})


if __name__=='__main__':
    main()
