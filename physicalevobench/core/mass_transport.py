"""Six short paired diagnostic attempts; no algorithm or task-parameter tuning."""

import argparse
from pathlib import Path

from physicalevobench.core.runtime import NativeSession
from physicalevobench.core.state_config import reference,worker_config
from physicalevobench.doctor import command,save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import load


def run(root,out):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Freeze mass transport diagnostic source')
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    base=reference(load(root/'configs/core/frozen_reference.json'))
    base.update(task_version='esl-initialization-diagnostic-v1',horizon_s=1.,scoring='support-diagnostic-no-learning')
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'registration.json',{'schema':'esl-model-transport-diagnostic-1','at':now(),'source_commit':source,
              'physical_budget':6,'A_short_attempts_before':30,'A_short_cap':48,'masses':[.1,.4,.1],
              'conditions':'Fixed seed315924514 and held joints/open gripper. Two new processes: readback observer, synchronized CPU-input reapply observer.',
              'motivation':'Readback .4kg with .981N and reverse-switch .1kg with3.924N seen before query. Diagnose model transport, not optimize score. Observers themselves may change timing.',
              'intervention':'Sync and reapply the same CPU mass/inertia/indices after the existing setter; no backend source changes; diagnostic only'})
    save_json(out/'status.json',{'status':'RUNNING'})
    for corrected in (False,True):
        cfg={**worker_config(base,3),'diagnostic_sync_reapply':corrected}
        session=NativeSession(root,out/('sync-reapply' if corrected else 'observer'),source,cfg,2,
                              module='physicalevobench.core.mass_transport_worker')
        try:
            session.ready()
            for i,mass in enumerate((.1,.4,.1)):
                session.trial({'episode_id':f'mass-{i}','condition':{'condition_id':f'transport-{i}',
                   'split':'initialization-diagnostic','seed':315924514,'object_mass_kg':mass},
                   'diagnostic_hold':True,'reference_config':base['reference_config'],
                   'identity':{'diagnostic':'parameter-transport','synchronized_reapply':corrected}})
        finally:
            session.close()
    save_json(out/'status.json',{'status':'COMPLETED','at':now()})


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    a=p.parse_args()
    run(Path.cwd(),Path(a.output))


if __name__=='__main__':
    main()
