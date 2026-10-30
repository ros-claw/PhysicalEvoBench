"""Finite same-problem qualification for the new state-only Ready execution."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.execution_identity import EXECUTION_FILES
from physicalevobench.core.problem import PROFILE,fresh
from physicalevobench.core.program import Program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.core.state_config import PROFILE as READY_INITIALIZATION,TASK,reference,worker_config
from physicalevobench.development.place import make_job,starter_program
from physicalevobench.doctor import command,save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import digest,load

READY_FILES=(*EXECUTION_FILES,'physicalevobench/core/readiness.py',
             'physicalevobench/core/state_config.py','physicalevobench/core/scene_diagnostics.py',
             'physicalevobench/core/errors.py','physicalevobench/core/parameter_transport.py')
READY_PROFILE={**PROFILE,'execution_profile':'state-ready2/contact-integral-v1',
               'task_version':TASK,'initialization_profile':READY_INITIALIZATION}


def run(root,out,gpu):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Freeze qualification source first')
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    base=reference(load(root/'configs/core/frozen_reference.json'))
    strong=Program.from_dict(json.loads((root/'configs/learning/reference_aperture.json').read_text()))
    programs={'starter':starter_program(),'strong':strong,'identity_strong':strong}
    cs=fresh(root,out.parent,2026103031,4,PROFILE['query_goal_positions'],'ready-qualification')
    jobs=[]
    for i,c in enumerate(cs):
        names=list(programs)
        for name in names[i%3:]+names[:i%3]:
            job=make_job(programs[name],c,f'qual-{len(jobs):03d}',name)
            job['reference_config']=base['reference_config']
            jobs.append(job)
    for c in cs[:2]:
        job=make_job(strong,c,f'qual-{len(jobs):03d}','force_open')
        job.update(reference_config=base['reference_config'],force_open=True)
        jobs.append(job)
    out.mkdir(parents=True,exist_ok=False)
    cfg=worker_config(base,len(jobs))
    save_json(out/'registration.json',{'schema':'esl-ready-qualification-1','at':now(),'source_commit':source,
              'profile':READY_PROFILE,'reference':base,'jobs':jobs,'physical_budget':14,'cfg':cfg,
              'criterion':'All 14 valid; strong 4/4; force-open 0/2; zero hard boundary. Starter and identical-graph replay measured, no required algorithm gain or starter failure.'})
    save_json(out/'status.json',{'status':'RUNNING'})
    session=NativeSession(root,out/'native',source,cfg,gpu)
    try:
        session.ready()
        for job in jobs:
            session.trial(job)
    finally:
        session.close()
    rows=audit_session(out/'native')
    valid=[r for r in rows if r['execution_status']!='INIT_INVALID']
    scores={name:[r['success'] for r in valid if r['core_identity']['method']==name]
            for name in (*programs,'force_open')}
    qualified=(len(valid)==14 and scores['strong']==[True]*4 and scores['force_open']==[False]*2
               and not any(r['diagnostic']['hard_boundary_terminated'] for r in valid))
    by_condition={name:{r['condition_id']:r['success'] for r in valid if r['core_identity']['method']==name}
                  for name in programs}
    common=set(by_condition['strong'])&set(by_condition['identity_strong'])
    identity=json.loads((out/'native/source_identity.json').read_text())
    receipt={'schema':'esl-ready-qualification-receipt-1','status':'QUALIFIED' if qualified else 'DEV',
             'source_commit':source,'at':now(),'learning_problem':READY_PROFILE,'learning_problem_sha256':digest(READY_PROFILE),
             'registration_sha256':digest(json.loads((out/'registration.json').read_text())),
             'initial_reference_sha256':digest(base),'starter_hash':starter_program().sha256,
             'reference_hash':strong.sha256,'scores':scores,'valid_attempts':len(valid),'assigned_attempts':14,
             'identity_discordances':sum(by_condition['strong'][c]!=by_condition['identity_strong'][c] for c in common),
             'execution_files':{p:identity['files'][p] for p in READY_FILES},
             'scope':'Finite same-problem qualification, not cross-task validity or method efficacy'}
    save_json(out/'qualification.json',receipt)
    save_json(out/'status.json',{'status':'COMPLETED','at':now()})
    return receipt



def audit_receipt(out):
    reg=json.loads((out/'registration.json').read_text())
    receipt=json.loads((out/'qualification.json').read_text())
    rows=audit_session(out/'native')
    if len(rows)!=len(reg['jobs']) or len(rows)!=14:
        raise ValueError('Qualification allocation incomplete')
    for i,job in enumerate(reg['jobs']):
        if json.loads((out/'native/requests'/f'{i:03d}.json').read_text())!=job:
            raise ValueError('Qualification differs from registered interventions')
    valid=[r for r in rows if r['execution_status']!='INIT_INVALID']
    scores={name:[r['success'] for r in valid if r['core_identity']['method']==name]
            for name in ('starter','strong','identity_strong','force_open')}
    qualified=(len(valid)==14 and scores['strong']==[True]*4 and scores['force_open']==[False]*2
               and not any(r['diagnostic']['hard_boundary_terminated'] for r in valid))
    identity=json.loads((out/'native/source_identity.json').read_text())
    if (receipt['scores']!=scores or receipt['status']!=('QUALIFIED' if qualified else 'DEV') or
            receipt['registration_sha256']!=digest(reg) or
            receipt['initial_reference_sha256']!=digest(reg['reference']) or
            receipt['learning_problem_sha256']!=digest(reg['profile']) or
            receipt['execution_files']!={p:identity['files'][p] for p in READY_FILES}):
        raise ValueError('Qualification receipt differs from registered/raw evidence')
    return {'status':'PASS','qualification_status':receipt['status'],'scores':scores,'attempts':len(rows)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--gpu',type=int,default=0)
    a=p.parse_args()
    print(json.dumps(run(Path.cwd(),Path(a.output),a.gpu),indent=2))


if __name__=='__main__':
    main()
