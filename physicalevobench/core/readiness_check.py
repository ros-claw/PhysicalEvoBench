"""Ready positive/explicit-fault conformance; no learning or model calls."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.runtime import NativeSession
from physicalevobench.core.state_config import reference,worker_config
from physicalevobench.doctor import command,save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import load


def run(root,out):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Freeze readiness diagnostic source first')
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    base=reference(load(root/'configs/core/frozen_reference.json'))
    base.update(task_version='esl-initialization-diagnostic-v1',horizon_s=1.,scoring='support-diagnostic-no-learning')
    groups=[{'name':'normal','disable_table':False,'masses':[.1,.1,.4,.1],'seeds':[315924514,903479326,1043475064,315924514]},
            {'name':'fault-injected','disable_table':True,'masses':[.1,.4],'seeds':[315924514,1043475064]}]
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'registration.json',{'schema':'esl-ready-conformance-1','source_commit':source,
              'at':now(),'physical_attempt_budget':6,'groups':groups,'base':base,
              'task_policy':'Fixed initial joints/open fingers. Fault injection explicitly disables table collision before construction. Not a spontaneous-fault reproduction. No retry, no model, no condition reselection.'})
    save_json(out/'status.json',{'status':'RUNNING'})
    result=[]
    for group in groups:
        cfg=worker_config(base,len(group['masses']))
        cfg['diagnostic_disable_table_collision']=group['disable_table']
        session=NativeSession(root,out/group['name'],source,cfg,2)
        try:
            session.ready()
            for i,(mass,seed) in enumerate(zip(group['masses'],group['seeds'],strict=True)):
                row=session.trial({'episode_id':f'check-{i}','condition':{'condition_id':f"{group['name']}-{i}",
                    'split':'ready-diagnostic','seed':seed,'object_mass_kg':mass},'diagnostic_hold':True,
                    'reference_config':base['reference_config'],'identity':{'diagnostic':group['name']}})
                ready=json.loads((out/group['name']/f'episodes/check-{i}/readiness.json').read_text())
                result.append({'group':group['name'],'slot':i,'execution_status':row['execution_status'],
                               'ready_status':ready['status'],'reason':ready['reason'],'task_controls':row['steps']})
        finally:
            session.close()
    passed=all(r['ready_status']==('INIT_INVALID' if r['group']=='fault-injected' else 'READY') for r in result)
    value={'status':'PASS' if passed else 'FAIL','cases':result,'attempts':len(result),
           'PPO_weights_used':False,'model_calls':0,'scope':'Fault injection validates detection, not spontaneous fault root cause'}
    save_json(out/'results.json',value)
    save_json(out/'status.json',{'status':'COMPLETED','at':now()})
    return value


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    a=p.parse_args()
    print(json.dumps(run(Path.cwd(),Path(a.output)),indent=2))


if __name__=='__main__':
    main()
