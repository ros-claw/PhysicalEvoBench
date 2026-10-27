"""Resume only preregistered stage gates; never retry failed confirmations."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from physicalevobench.doctor import save_json
from physicalevobench.evaluation.confirmation import now


def wait_complete(directory):
    while True:
        status=json.loads((directory/'status.json').read_text())
        if status['status'] not in ('QUEUED','RUNNING'):
            return status
        time.sleep(5)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--pilot',required=True)
    p.add_argument('--place-development',required=True)
    p.add_argument('--confirmation-output',required=True)
    p.add_argument('--flow-output',required=True)
    p.add_argument('--gpu',type=int,default=2)
    p.add_argument('--receipt',required=True)
    a=p.parse_args()
    pilot,development=Path(a.pilot),Path(a.place_development)
    confirmation,flow=Path(a.confirmation_output),Path(a.flow_output)
    status=wait_complete(development)
    if status['status']!='COMPLETED' or not json.loads((development/'place_results.json').read_text())['development_qualified']:
        save_json(a.receipt,{'status':'STOPPED_AT_DEVELOPMENT_GATE','at':now(),'no_confirmation_or_transfer_launched':True})
        return
    if confirmation.exists():
        raise ValueError('Refuse implicit retry/resume of an existing independent confirmation')
    command=[sys.executable,'-m','physicalevobench.core.place_study','--reference',
             str(development/'baseline_reference.json'),'--confirmation-development',str(development),
             '--output',str(confirmation),'--gpu',str(a.gpu)]
    with (confirmation.parent/(confirmation.name+'.launcher.log')).open('w') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode or not json.loads((confirmation/'place_results.json').read_text())['independent_gate_passed']:
        save_json(a.receipt,{'status':'STOPPED_AT_CONFIRMATION_GATE','at':now(),'confirmation_returncode':result.returncode,'no_transfer_launched':True})
        return
    if wait_complete(pilot)['status']!='COMPLETED':
        save_json(a.receipt,{'status':'STOPPED_AT_AGENT_PROTOCOL_GATE','at':now()})
        return
    if flow.exists():
        raise ValueError('Refuse implicit task-flow retry')
    command=[sys.executable,'-m','physicalevobench.core.flow','--pilot',str(pilot),
             '--confirmation',str(confirmation),'--output',str(flow),'--gpu',str(a.gpu)]
    with (flow.parent/(flow.name+'.launcher.log')).open('w') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    save_json(a.receipt,{'status':'COMPLETED' if result.returncode==0 else 'TASK_FLOW_FAILED',
                        'at':now(),'flow_returncode':result.returncode})


if __name__=='__main__':
    main()
