"""An actual generic stdin provider adapter using the existing Codex transport.

This is a second protocol integration, not a second model or agent framework.
Outer harness retains input/output/usage. Inner raw CLI receipts go to stderr.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from physicalevobench.core.learning import SCHEMA
from physicalevobench.core.model import ParticipantProcess


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',default='gpt-6.1-terra')
    a=p.parse_args()
    request=json.load(sys.stdin)
    with tempfile.TemporaryDirectory(prefix='peb-stdin-bridge-') as temp:
        out=Path(temp)/'inner'
        participant=ParticipantProcess(['codex'],a.model,out,max_calls=1,input_limit=300000,output_limit=48000,schema=SCHEMA)
        try:
            response=participant.call(request)
            usage=json.loads((out/'call-00/usage.json').read_text())
            print(json.dumps({'response':response,'usage':usage}),flush=True)
        finally:
            for path in sorted(out.rglob('*')):
                if path.is_file() and path.name in ('events.jsonl','stderr.log','process.json','usage.json'):
                    sys.stderr.write('\nINNER_RECEIPT '+str(path.relative_to(out))+'\n'+path.read_text())


if __name__=='__main__':
    main()
