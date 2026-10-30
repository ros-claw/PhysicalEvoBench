"""Lightweight public entry point; smoke never pretends to run physics."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from physicalevobench.core.program import Program, initial_program


def main():
    p=argparse.ArgumentParser(prog='physicalevobench-core')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('learn',help='Qualified executable-skill pilot with same-model controls')
    sub.add_parser('qualify',help='Independent task qualification')
    sub.add_parser('physical-smoke',help='Standalone real T0 episode; no T1 or historical run required')
    sub.add_parser('tasks',help='Independent task lifecycle and scope')
    sub.add_parser('smoke',help='CPU schema/guard smoke only; zero physical episodes')
    run=sub.add_parser('run',help='Run a bounded real-model P pilot using a prior calibration receipt')
    run.add_argument('--output',required=True)
    run.add_argument('--reference',default='configs/core/frozen_reference.json')
    run.add_argument('--calibration',default='configs/core/calibration-b1')
    run.add_argument('--gpu',type=int,default=2)
    run.add_argument('--model',default='gpt-6.1-terra')
    run.add_argument('--participant-command',help='JSON argv for a generic stdin provider')
    audit=sub.add_parser('audit',help='Recompute an existing evidence directory without physics')
    audit.add_argument('--run-dir',required=True)
    if len(sys.argv)>1 and sys.argv[1] in ('learn','qualify'):
        if sys.argv[1]=='learn':
            from physicalevobench.core.learning import main as entry
        else:
            from physicalevobench.core.problem import main as entry
        sys.argv.pop(1)
        return entry()
    if len(sys.argv)>1 and sys.argv[1]=='physical-smoke':
        from physicalevobench.core.standalone import main as physical_main
        sys.argv.pop(1)
        return physical_main()
    a=p.parse_args()
    if a.command=='tasks':
        from physicalevobench.core.tasks import TASKS,task
        print(json.dumps({k:task(k,'DEV') for k in TASKS},indent=2))
        return
    if a.command=='run':
        argv=[sys.executable,'-m','physicalevobench.core.pilot','--output',a.output,
              '--reference',a.reference,'--b1',a.calibration,'--gpu',str(a.gpu),'--model',a.model]
        if a.participant_command:
            argv+=['--participant-command',a.participant_command]
        raise SystemExit(subprocess.run(argv,check=False).returncode)
    if a.command=='smoke':
        for place in (False,True):
            program=initial_program(place)
            if Program.from_dict(program.to_dict()).sha256!=program.sha256:
                raise ValueError('Graph serialization changed')
        print(json.dumps({'status':'PASS','scope':'CPU contracts only','physical_episodes':0,
                          'tasks':['state-reference-h10-v1','core-place-h20-v2-dev'],
                          'physical_reference_validation':'not_run_by_this_CPU_command'}))
        return
    out=Path(a.run_dir)
    reg=json.loads((out/'registration.json').read_text())
    schema=reg['schema']
    if schema=='esl-problem-qualification-1':
        from physicalevobench.core.problem import audit_receipt
        result=audit_receipt(out)
    elif schema=='esl-frozen-extension-1':
        from physicalevobench.core.extension import summarize
        result=summarize(out)
    elif schema=='esl-learning-1':
        from physicalevobench.core.learning import summarize
        result=summarize(out)
    elif schema in ('esl-development-1','esl-qualification-1','core-standalone-smoke-1'):
        from physicalevobench.core.audit import audit_session
        data=audit_session(out/'native')
        result={'audit':'PASS','scope':'raw physical task scoring','episodes':len(data)}
    elif schema=='core-pilot-1':
        from physicalevobench.core.audit import audit_pilot
        result=audit_pilot(out)
    elif schema=='v02-diagnostics-1' and reg['phase']=='core-parameter-space-1':
        from physicalevobench.core.parameter_space import summarize
        result=summarize(out)
    elif schema=='core-flow-1':
        from physicalevobench.core.flow import summarize
        result=summarize(out)
    elif schema=='core-place-study-1':
        from physicalevobench.core.audit import audit_session
        data=audit_session(out/'native')
        result={'audit':'PASS','scope':'raw physical task scoring','episodes':len(data)}
    else:
        raise ValueError('Unsupported Core study schema')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
