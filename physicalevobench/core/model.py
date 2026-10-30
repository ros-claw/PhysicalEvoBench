"""Generic stdin/stdout participant transport and an optional Codex CLI backend.

No evaluator filesystem path or secret is serialized into the model request.
CLI events are preserved; auth is owned by the installed CLI, never read here.
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path

from physicalevobench.doctor import save_json
from physicalevobench.evaluation.confirmation import now


CALL_SCHEMA={
    'type':'object','additionalProperties':False,
    'properties':{'tool':{'type':'string','enum':['run_trial','freeze']},
                  'approach_clearance_m':{'type':'number','minimum':.08,'maximum':.12},
                  'minimum_close_s':{'type':'number','minimum':.2,'maximum':.7},
                  'training_condition_handle':{'type':'string'},
                  'memory':{'type':'string','maxLength':4000}},
    'required':['tool','approach_clearance_m','minimum_close_s','training_condition_handle','memory']}


class ParticipantProcess:
    def __init__(self,command,model,log_dir,max_calls=12,input_limit=250000,output_limit=24000,schema=None):
        self.schema=schema or CALL_SCHEMA
        self.command,self.model,self.log_dir=command,model,Path(log_dir)
        self.log_dir.mkdir(parents=True,exist_ok=False)
        self.calls,self.input_tokens,self.output_tokens=0,0,0
        self.max_calls,self.input_limit,self.output_limit=max_calls,input_limit,output_limit

    def call(self,request):
        if self.calls>=self.max_calls or self.input_tokens>=self.input_limit or self.output_tokens>=self.output_limit:
            raise ValueError('Participant computational budget exhausted')
        index=self.calls
        self.calls+=1
        directory=self.log_dir/f'call-{index:02d}'
        directory.mkdir()
        save_json(directory/'request.json',request)
        started=time.monotonic()
        started_at=now()
        with tempfile.TemporaryDirectory(prefix='peb-participant-') as temporary:
            tmp=Path(temporary)
            if self.command==['codex']:
                save_json(tmp/'schema.json',self.schema)
                argv=['codex','exec','--ignore-user-config','--ignore-rules','--ephemeral',
                      '--skip-git-repo-check','-s','read-only','-C',temporary,
                      '-c','features.shell_tool=false','-c','features.multi_agent=false',
                      '-c','web_search="disabled"','-m',self.model,'--json',
                      '--output-schema',str(tmp/'schema.json'),'-o',str(tmp/'answer.json'),'-']
            else:
                argv=self.command
            save_json(directory/'reservation.json',{'call':index,'model':self.model,'timeout_s':120,'started_at':started_at})
            with (directory/'events.jsonl').open('w') as stdout,(directory/'stderr.log').open('w') as stderr:
                try:
                    result=subprocess.run(argv,input=json.dumps(request),text=True,cwd=tmp,
                                          stdout=stdout,stderr=stderr,timeout=120)
                except subprocess.TimeoutExpired:
                    save_json(directory/'process.json',{'returncode':None,'timeout':True,'wall_s':time.monotonic()-started,'started_at':started_at,'finished_at':now(),'usage':'unknown'})
                    raise
            save_json(directory/'process.json',{'returncode':result.returncode,'wall_s':time.monotonic()-started,'started_at':started_at,'finished_at':now()})
            events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
            if result.returncode:
                raise RuntimeError('Participant transport failed; see preserved process evidence')
            if self.command==['codex']:
                usage=[e['usage'] for e in events if e.get('type')=='turn.completed']
                if len(usage)!=1:
                    raise ValueError('Exactly one reported model usage record required')
                # Reject any actual built-in tool action: only returned benchmark
                # calls are permitted, never local shell/MCP/web actions.
                if any(e.get('type')=='item.completed' and e.get('item',{}).get('type') not in
                       ('agent_message','reasoning') for e in events):
                    raise ValueError('Participant used an undeclared built-in tool')
                answer=json.loads((tmp/'answer.json').read_text())
            else:
                if len(events)!=1 or set(events[0])!={'response','usage'}:
                    raise ValueError('Generic participant must return response and actual usage')
                answer,usage=events[0]['response'],[events[0]['usage']]
            for key in ('input_tokens','output_tokens'):
                if type(usage[0].get(key)) is not int or usage[0][key]<0:
                    raise ValueError('Actual nonnegative integer provider usage required')
            self.input_tokens+=usage[0]['input_tokens']
            self.output_tokens+=usage[0]['output_tokens']
            save_json(directory/'response.json',answer)
            save_json(directory/'usage.json',usage[0])
        save_json(self.log_dir/'budget.json',{'calls':self.calls,'input_tokens':self.input_tokens,
                                            'output_tokens':self.output_tokens})
        if self.input_tokens>self.input_limit or self.output_tokens>self.output_limit:
            raise ValueError('Participant exceeded cumulative token cap; run invalid')
        return answer
