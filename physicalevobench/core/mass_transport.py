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


def audit_result(out):
    import json

    from physicalevobench.core.parameter_transport import flat
    from physicalevobench.core.readiness_audit import audit_readiness
    from physicalevobench.v02.audit import episode_metrics

    def read(path):
        return json.loads(path.read_text())
    reg=read(out/'registration.json')
    result={}
    for name in ('observer','sync-reapply'):
        native=out/name
        if read(native/'process.json')['returncode']!=0:
            raise ValueError('Model transport native process failed')
        events=read(native/'model_parameter_transport.json')
        mismatches=[]
        for event in events:
            phys=event['after_optional_synchronized_reapply']
            for key in ('mass','inertia'):
                if max(abs(a-b) for a,b in zip(flat(phys[key]),flat(event['gpu_shadow'][key]),strict=True))>1e-8:
                    mismatches.append({'event':event['method'],'kind':key,'physx':phys[key],'shadow':event['gpu_shadow'][key]})
        rows=[]
        for i,mass in enumerate(reg['masses']):
            job=read(native/'requests'/f'{i:03d}.json')
            row=read(native/'responses'/f'{i:03d}.json')
            ep=native/'episodes'/job['episode_id']
            if job['condition']['object_mass_kg']!=mass or job['condition']['seed']!=315924514:
                raise ValueError('Parameter diagnostic changed nominal condition')
            audit_readiness(ep,job['condition'],row)
            if row['execution_status']=='OK' and row['diagnostic']!=episode_metrics(ep,native/'control_semantics.json'):
                raise ValueError('Held parameter diagnostic differs from raw physics')
            rows.append(row)
        result[name]={'attempts':len(rows),'parameter_mismatches':mismatches,
                      'ready_statuses':[r['execution_status'] for r in rows]}
    stored=read(out/'results.json')
    if stored['results']!=result:
        raise ValueError('Model transport conclusion differs from raw getter/setter evidence')
    return {'audit':'PASS','results':result,'scope':stored['scope']}
