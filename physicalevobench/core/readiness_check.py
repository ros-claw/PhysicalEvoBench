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
                               'ready_status':ready['status'],'reason':ready['reason'],'task_controls':row['steps'],
                               'runtime_table_shape_hit':ready['runtime_shapes_after']['table_shape_hit']})
        finally:
            session.close()
    passed=all(r['ready_status']==('INIT_INVALID' if r['group']=='fault-injected' else 'READY')
               and r['runtime_table_shape_hit']==(r['group']=='normal') for r in result)
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


def audit_result(out):
    from physicalevobench.core.readiness_audit import audit_readiness
    from physicalevobench.doctor import sha256
    from physicalevobench.v02.audit import episode_metrics,records

    def read(path):
        return json.loads(path.read_text())
    reg=read(out/'registration.json')
    stored=read(out/'results.json')
    cases=[]
    for group in reg['groups']:
        native=out/group['name']
        if read(native/'process.json')['returncode']!=0:
            raise ValueError('Conformance native process did not close successfully')
        for i,(mass,seed) in enumerate(zip(group['masses'],group['seeds'],strict=True)):
            job=read(native/'requests'/f'{i:03d}.json')
            if job['condition']['seed']!=seed or job['condition']['object_mass_kg']!=mass:
                raise ValueError('Conformance changed registered condition')
            episode=native/'episodes'/f'check-{i}'
            row=read(episode/'episode.json')
            ready=read(episode/'readiness.json')
            audit_readiness(episode,job['condition'],row)
            if row['execution_status']!='INIT_INVALID':
                if row['diagnostic']!=episode_metrics(episode,native/'control_semantics.json'):
                    raise ValueError('Held conformance physics differs from raw trace')
                trace=records(native/row['trace_artifact'])
                if (sha256(native/row['trace_artifact'])!=row['trace_sha256'] or len(trace)!=row['steps'] or
                        any(t['policy_diagnostics'].get('diagnostic_control')!='fixed_initial_joint_target_open_gripper' for t in trace)):
                    raise ValueError('Conformance used a participant/approach action')
            cases.append({'group':group['name'],'slot':i,'execution_status':row['execution_status'],
                          'ready_status':ready['status'],'reason':ready['reason'],'task_controls':row['steps'],
                          'runtime_table_shape_hit':ready['runtime_shapes_after']['table_shape_hit']})
    for raw,recorded in zip(cases,stored['cases'],strict=True):
        if any(raw[key]!=value for key,value in recorded.items()):
            raise ValueError('Conformance case changed')
    passed=all(r['ready_status']==('INIT_INVALID' if r['group']=='fault-injected' else 'READY') and
               r['runtime_table_shape_hit']==(r['group']=='normal') for r in cases)
    if stored['status']!=('PASS' if passed else 'FAIL') or stored['attempts']!=len(cases):
        raise ValueError('Conformance outcome differs from physical evidence')
    return {'audit':'PASS','conformance_status':stored['status'],'attempts':len(cases),
            'scope':'Evidence verification; an ineffective historical fault injection remains FAIL, not a passed detector test'}
