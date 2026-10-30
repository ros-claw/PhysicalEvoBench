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


def run(root,out,qualification,gpu,provider=None,model='gpt-6.1-terra'):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Freeze adapter smoke source first')
    q,base=validate_contract(root,qualification)
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    group=manifest(root,out.parent,1,profile=q['learning_problem'],stream=2026103034)[0]
    provider=provider or [sys.executable,'-m','physicalevobench.core.stdin_adapter','--model',model]
    cfg=worker_config(base,1)
    out.mkdir(parents=True,exist_ok=False)
    run_id='adapter-smoke/'+str(uuid.uuid4())
    save_json(out/'registration.json',{'schema':'esl-state-stdin-smoke-1','at':now(),'mode':'INTEGRATION_SMOKE',
              'source_commit':source,'physical_budget':1,'model':model,'provider':provider,
              'conditions':group,'reference':base,'qualification':q,
              'scope':'Same-machine new source/CPU venv and generic stdin integration; no efficacy estimate, no second model/framework/machine/person claim'})
    save_json(out/'status.json',{'status':'DESIGNING'})
    result=learn(root,out,source,cfg,base,group,'designer',model,provider,run_id,gpu)
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
    p.add_argument('--provider',help='JSON argv for a generic stdin participant; default is the tested CLI bridge')
    p.add_argument('--model',default='gpt-6.1-terra')
    a=p.parse_args()
    print(json.dumps(run(Path.cwd(),Path(a.output),Path(a.qualification),a.gpu,json.loads(a.provider) if a.provider else None,a.model),indent=2))


if __name__=='__main__':
    main()


def audit_result(out):
    from physicalevobench.core.artifact import load as load_artifact
    from physicalevobench.core.audit import assert_public
    from physicalevobench.core.learning import compact
    from physicalevobench.v02.reference_artifact import digest

    def read(path):
        return json.loads(path.read_text())
    reg=read(out/'registration.json')
    data=audit_session(out/'native')
    if len(data)!=1 or read(out/'registered_job.json')!=read(out/'native/requests/000.json'):
        raise ValueError('Stdin integration differs from reserved physical request')
    art=load_artifact(out/'designer/artifact.json')
    frozen=read(out/'all_frozen.json')
    job=read(out/'registered_job.json')
    source=read(out/'native/source_identity.json')
    if (source['commit']!=reg['source_commit'] or job['program']!=art['payload']['skill'] or
            job['identity']['effective_artifact_hash']!=art['effective_artifact_hash'] or
            frozen['artifact_hash']!=art['effective_artifact_hash'] or
            art['payload']['initial_reference']!=digest(reg['reference']) or
            read(out/'native/launch.json')['started_at']<=frozen['at']):
        raise ValueError('Stdin frozen artifact identity or freeze boundary changed')
    if any(source['files'][p]!=value for p,value in reg['qualification']['execution_files'].items()):
        raise ValueError('Portable execution differs from qualified code')
    receipt=read(out/'designer/freeze_receipt.json')
    selected=read(out/'designer'/f"proposal-{receipt['proposal_index']:02d}.json")
    if (selected['tool']!='freeze' or json.loads(selected['program_json'])!=art['payload']['skill'] or
            selected['memory']!=art['payload']['memory'] or (out/'designer/native').exists()):
        raise ValueError('NoFeedback adapter did not select frozen artifact in isolation')
    history=read(out/'designer/history.json') if (out/'designer/history.json').exists() else []
    calls=sorted((out/'designer/model_calls').glob('call-*'))
    usages=[]
    for i,call in enumerate(calls):
        request=read(call/'request.json')
        assert_public(request)
        if request['history']!=compact(history[:i]):
            raise ValueError('Adapter history differs from actual prior proposals')
        envelopes=[json.loads(s) for s in (call/'events.jsonl').read_text().splitlines()]
        usage=read(call/'usage.json')
        if len(envelopes)!=1 or envelopes[0]['usage']!=usage or envelopes[0]['response']!=read(call/'response.json'):
            raise ValueError('Generic stdin envelope differs from retained response/usage')
        usages.append(usage)
    budget=read(out/'designer/model_calls/budget.json')
    if budget!={'calls':len(calls),'input_tokens':sum(u['input_tokens'] for u in usages),
               'output_tokens':sum(u['output_tokens'] for u in usages)}:
        raise ValueError('Adapter actual computation differs from budget receipt')
    result=read(out/'result.json')
    if result['task_success']!=data[0]['success'] or result['task_controls']!=data[0]['steps']:
        raise ValueError('Adapter result differs from raw task execution')
    return {'audit':'PASS','physical_attempts':1,'task_success':data[0]['success'],
            'task_controls':data[0]['steps'],'model_calls':len(calls),
            'scope':'Generic stdin envelope, actual usage, selected artifact, independent source/qualification and real physics; same-machine only'}
