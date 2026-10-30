"""Small no-weight stdin integration: design, freeze, independent physical execution."""

import argparse
import json
import sys
import uuid
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.artifact import load as load_artifact
from physicalevobench.core.learning import learn,manifest
from physicalevobench.core.program import Program
from physicalevobench.core.replication import validate_contract
from physicalevobench.core.runtime import NativeSession
from physicalevobench.core.state_config import worker_config
from physicalevobench.development.place import make_job
from physicalevobench.doctor import command,save_json
from physicalevobench.evaluation.confirmation import now


def run(root,out,qualification,gpu):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Freeze adapter smoke source first')
    q,base=validate_contract(root,qualification)
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    group=manifest(root,out.parent,1,profile=q['learning_problem'],stream=2026103034)[0]
    provider=[sys.executable,'-m','physicalevobench.core.stdin_adapter','--model','gpt-6.1-terra']
    cfg=worker_config(base,1)
    out.mkdir(parents=True,exist_ok=False)
    run_id='adapter-smoke/'+str(uuid.uuid4())
    save_json(out/'registration.json',{'schema':'esl-state-stdin-smoke-1','at':now(),'mode':'INTEGRATION_SMOKE',
              'source_commit':source,'physical_budget':1,'model':'gpt-6.1-terra','provider':provider,
              'conditions':group,'reference':base,'qualification':q,
              'scope':'Same-machine new source/CPU venv and generic stdin integration; no efficacy estimate, no second model/framework/machine/person claim'})
    save_json(out/'status.json',{'status':'DESIGNING'})
    result=learn(root,out,source,cfg,base,group,'designer','gpt-6.1-terra',provider,run_id,gpu)
    if result is None:
        save_json(out/'status.json',{'status':'PARTICIPANT_INVALID','physical_episodes':0})
        return {'status':'PARTICIPANT_INVALID'}
    persisted=load_artifact(out/'designer/artifact.json')
    program=Program.from_dict(persisted['payload']['skill'])
    save_json(out/'all_frozen.json',{'at':now(),'artifact_hash':persisted['effective_artifact_hash']})
    job=make_job(program,group['query'][0],'adapter-smoke-000','stdin-adapter-smoke')
    job['reference_config']=base['reference_config']
    job['identity']['effective_artifact_hash']=persisted['effective_artifact_hash']
    save_json(out/'registered_job.json',job)
    session=NativeSession(root,out/'native',source,cfg,gpu)
    try:
        session.ready()
        row=session.trial(job)
    finally:
        session.close()
    data=audit_session(out/'native')
    result={'status':'PASS' if row['execution_status']=='OK' else 'INIT_INVALID','physical_attempts':len(data),
            'task_success':row['success'],'task_controls':row['steps'],'PPO_weights_used':False,
            'model_calls':len(list((out/'designer/model_calls').glob('call-*'))),
            'scope':'Protocol and real execution integration only; task failure would not by itself fail engineering integration.'}
    save_json(out/'result.json',result)
    save_json(out/'status.json',{'status':'COMPLETED','at':now()})
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--qualification',default='configs/reliability/qualification.json')
    p.add_argument('--gpu',type=int,default=2)
    a=p.parse_args()
    print(json.dumps(run(Path.cwd(),Path(a.output),Path(a.qualification),a.gpu),indent=2))


if __name__=='__main__':
    main()
