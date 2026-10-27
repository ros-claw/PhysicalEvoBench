"""Lightweight public entry point; smoke never pretends to run physics."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.program import Program, initial_program


def main():
    p=argparse.ArgumentParser(prog='physicalevobench-core')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('smoke',help='CPU schema/guard smoke only; zero physical episodes')
    audit=sub.add_parser('audit',help='Recompute an existing evidence directory without physics')
    audit.add_argument('--run-dir',required=True)
    a=p.parse_args()
    if a.command=='smoke':
        for place in (False,True):
            program=initial_program(place)
            if Program.from_dict(program.to_dict()).sha256!=program.sha256:
                raise ValueError('Graph serialization changed')
        print(json.dumps({'status':'PASS','scope':'CPU contracts only','physical_episodes':0,
                          'tasks':['state-reference-h10-v1','core-place-h20-v2-dev'],
                          'S_graph_reference_calibrated':False}))
        return
    out=Path(a.run_dir)
    reg=json.loads((out/'registration.json').read_text())
    schema=reg['schema']
    if schema=='core-pilot-1':
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
