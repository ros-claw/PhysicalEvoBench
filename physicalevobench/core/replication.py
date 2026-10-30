"""Fixed eight-block same-version replication, freeze all learning before any query."""

import argparse
import concurrent.futures
import inspect
import json
import uuid
from datetime import datetime
from pathlib import Path

from physicalevobench.core.artifact import executable_fingerprint,freeze,load as load_artifact
from physicalevobench.core.audit import audit_session
from physicalevobench.core.learning import INSTRUCTIONS,SCHEMA,artifact,compact,learn,manifest,score_search,search_candidates
from physicalevobench.core.learning_audit import audit_bindings
from physicalevobench.core.program import Program
from physicalevobench.core.ready_qualification import READY_FILES,READY_PROFILE
from physicalevobench.core.replication_metrics import ARMS,LABELS,execution_chain,summarize
from physicalevobench.core.runtime import NativeSession,atomic_json
from physicalevobench.core.state_config import reference,worker_config
from physicalevobench.development.place import make_job,starter_program
from physicalevobench.doctor import command,save_json,sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import digest,load


def artifact_path(directory,name):
    return directory/(f'{name}.json' if name in ('frozen','deletion') else f'{name}/artifact.json')


def validate_contract(root,qualification):
    q=json.loads(qualification.read_text())
    base=reference(load(root/'configs/core/frozen_reference.json'))
    if (q['status']!='QUALIFIED' or q['learning_problem_sha256']!=digest(READY_PROFILE) or
            q['initial_reference_sha256']!=digest(base) or q['starter_hash']!=starter_program().sha256 or
            set(q['execution_files'])!=set(READY_FILES)):
        raise ValueError('New execution needs its own complete physical qualification')
    for p in READY_FILES:
        if sha256(root/p)!=q['execution_files'][p]:
            raise ValueError('Qualified execution changed: '+p)
    frozen=json.loads((root/'configs/reliability/public_context_v3.json').read_text())
    if frozen['instructions']!=INSTRUCTIONS or frozen['response_schema']!=SCHEMA or frozen['compaction_source']!=inspect.getsource(compact):
        raise ValueError('public-context-v3 contract changed')
    return q,base


def run(root,out,qualification,gpus,query_lanes_per_gpu=2):
    if not gpus or query_lanes_per_gpu not in (1,2):
        raise ValueError('Choose one or two predeclared query lanes per GPU')
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit replication implementation before registration')
    q,base=validate_contract(root,qualification)
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    groups=manifest(root,out.parent,8,profile=READY_PROFILE,stream=2026103033,query_repeats=4)
    cfg={**worker_config(base,8),'save_sparse_snapshots':True}
    study_id=str(uuid.uuid4())
    orders=[list(ARMS)[i%5:]+list(ARMS)[:i%5] for i in range(8)]
    query_orders=[{a:[(j+3*i+3*k)%16 for j in range(16)] for k,a in enumerate(ARMS)} for i in range(8)]
    out.mkdir(parents=True,exist_ok=False)
    reg={'schema':'esl-replication-1','at':now(),'study_id':study_id,'source_commit':source,'instances':8,
         'conditions':groups,'query_arm_orders':orders,'query_order_by_arm':query_orders,
         'participant_context_version':'public-context-v3','instructions_sha256':digest({'instructions':INSTRUCTIONS}),
         'context_contract_sha256':sha256(root/'configs/reliability/public_context_v3.json'),
         'asset_dependency_snapshot_sha256':sha256(root/'configs/reliability/asset_dependencies.json'),
         'asset_dependency_scope':'Serialized content SHA256 for 23 resolved USD layers; same-machine provenance. OmniPBR.mdl unresolved in this read-only resolver, non-layer texture bytes not hashed. No vision or complete cross-machine asset equivalence claim.',
         'executor_prefix':'state-ready2/contact-integral-v1/','condition_stream':2026103033,
         'learning_problem':READY_PROFILE,'qualification':q,'qualification_sha256':sha256(qualification),
         'reference':base,'cfg':cfg,'model':'gpt-6.1-terra','provider':['codex'],
         'provider_cli_version':command(['codex','--version']),
         'model_limits_per_method':{'calls':10,'input_tokens':300000,'output_tokens':48000},
         'physical_budget':768,'ready_probe_substeps_per_attempt':200,'gpus':gpus,
         'concurrency':{'training_lanes':len(gpus),'query_lanes':len(gpus)*query_lanes_per_gpu,'query_lanes_per_gpu':query_lanes_per_gpu,
                        'reason':'Pre-outcome resource plan; task dt/controls unchanged; independent native process per arm/block; shared GPU workload receipts retained'},
         'method_labels':LABELS,'method_order':[(['designer','feedback'] if i%2==0 else ['feedback','designer']) for i in range(8)],
         'search':{'name':'TemplateSearch-4 / Expert-Prior Search','human_prior':'Four hand-structured release/place graph variants; not blind random search',
                   'programs':[p.to_dict() for p in search_candidates()],'practice_indices':[0,1],'selection':'largest score; earliest tie'},
         'comparison':'budget-cap comparison; natural early freeze; actual computation unequal',
         'retry_limits':{'provider':0,'physics':0},'missing_rule':'No reseed or favorable replacement. Provider/infra failure stays incomplete; participant invalid stays assigned failure. Show valid-task and all-assigned separately.',
         'statistics':'8 outer independent learning blocks; paired goal/mass-cell stratified hierarchical bootstrap; identity discordance, not net difference',
         'optional_diagnostics':{'DeliberationOnly-9':'NOT_RUN; prioritize fixed 8-block main experiment','B2_B4_query_curves':'NOT_RUN; only no-extra-call snapshots'},
         'inference_identity':'Requested model identifier and actual CLI receipts; provider effort/fingerprint/immutable weights unavailable, not guaranteed constant'}
    save_json(out/'registration.json',reg)
    save_json(out/'status.json',{'status':'LEARNING','at':now()})
    def train(i,gpu):
        directory=out/f'instance-{i}'
        directory.mkdir()
        run_id=f'{study_id}/instance-{i}'
        values={}
        for name in ('frozen','deletion'):
            values[name]=freeze(artifact(base,starter_program(),source,run_id,name,0,''),artifact_path(directory,name))
        for name in [*reg['method_order'][i],'search']:
            try:
                value=(score_search(root,directory,source,cfg,base,groups[i],run_id,gpu) if name=='search' else
                       learn(root,directory,source,cfg,base,groups[i],name,'gpt-6.1-terra',['codex'],run_id,gpu))
                values[name]=value if value is not None else 'INVALID_PARTICIPANT_SUBMISSION'
            except Exception as error:
                status=getattr(error,'category','UNKNOWN_FAILURE')
                save_json(directory/name/'method_failure.json',{'status':status,'reason':str(error),'at':now(),'retry_limit':0})
                values[name]=status
            print(json.dumps({'phase':'learning','block':i,'method':name,'result':values[name]['effective_artifact_hash'] if isinstance(values[name],dict) else values[name]}),flush=True)
        value={n:v['effective_artifact_hash'] if isinstance(v,dict) else v for n,v in values.items()}
        atomic_json(directory/'learning_complete.json',{'at':now(),'artifacts':value})
    def gpu_training(k):
        for i in range(k,8,len(gpus)):
            train(i,gpus[k])
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(gpus)) as pool:
        list(pool.map(gpu_training,range(len(gpus))))
    all_frozen={'at':now(),'artifacts':[json.loads((out/f'instance-{i}/learning_complete.json').read_text())['artifacts'] for i in range(8)]}
    save_json(out/'all_frozen.json',all_frozen)
    save_json(out/'status.json',{'status':'QUERY','at':now()})
    def evaluate(i,gpu):
        directory=out/f'instance-{i}'
        for name in orders[i]:
            path=artifact_path(directory,name)
            if not path.exists() or (directory/name/'method_failure.json').exists():
                continue
            persisted=load_artifact(path)
            if persisted['effective_artifact_hash']!=all_frozen['artifacts'][i][name]:
                raise ValueError('Artifact changed after all-block freeze')
            program=Program.from_dict(persisted['payload']['skill'])
            session=None
            try:
                try:
                    session=NativeSession(root,directory/f'test-{name}',source,{**cfg,'physical_budget':16},gpu)
                    session.ready()
                    for j in query_orders[i][name]:
                        c=groups[i]['query'][j]
                        job=make_job(program,c,f'query-{j:03d}',name)
                        job['reference_config']=base['reference_config']
                        job['identity'].update(effective_artifact_hash=persisted['effective_artifact_hash'],
                                               learning_run_id=persisted['payload']['learning_run_id'])
                        session.trial(job)
                finally:
                    if session is not None:
                        session.close()
            except Exception as error:
                save_json(directory/f'test-{name}'/'query_failure.json',{'status':getattr(error,'category','UNKNOWN_FAILURE'),
                          'reason':str(error),'at':now(),'retry_limit':0,
                          'score_policy':'Entire incomplete query arm reported missing; raw completed prefix retained, no favorable replacement.'})
            print(json.dumps({'phase':'query','block':i,'method':name,'status':'INCOMPLETE' if (directory/f'test-{name}'/'query_failure.json').exists() else 'COMPLETED'}),flush=True)
    query_lanes=len(gpus)*query_lanes_per_gpu
    def gpu_query(k):
        for i in range(k,8,query_lanes):
            evaluate(i,gpus[k%len(gpus)])
    with concurrent.futures.ThreadPoolExecutor(max_workers=query_lanes) as pool:
        list(pool.map(gpu_query,range(query_lanes)))
    result=audit_and_summarize(out)
    save_json(out/'status.json',{'status':'COMPLETED','at':now()})
    return result


def audit_and_summarize(out):
    reg=json.loads((out/'registration.json').read_text())
    frozen=json.loads((out/'all_frozen.json').read_text())
    binding=audit_bindings(out,reg,frozen)
    blocks=[]
    audited={}
    def audit_native(path):
        if str(path) not in audited:
            audited[str(path)]=audit_session(path)
        return audited[str(path)]
    totals={'task_attempts':0,'task_controls':0,'task_physics_substeps':0,'ready_physics_substeps':0,'init_invalid':0,'native_processes':0,'native_process_seconds':0.,'native_processes_missing_timing':0,
            'reserved_task_attempts':0,'uncompleted_reserved_attempts':0,'unverified_completed_task_attempts':0,
            'hard_boundary_episodes':0,'position_violation_episodes':0,'limited_task_controls':0}
    for i,group in enumerate(reg['conditions']):
        directory=out/f'instance-{i}'
        block={'block':i,'conditions':group['query'],'scores':{},'execution_statuses':{},'model_cost':{},'method_failures':{},'retained_artifacts':{},'execution_effects':{}}
        for name in ARMS:
            native=directory/f'test-{name}'
            scores={c['condition_id']:None for c in group['query']}
            statuses={c['condition_id']:'METHOD_INCOMPLETE' for c in group['query']}
            if native.exists() and not (native/'query_failure.json').exists():
                if json.loads((native/'launch.json').read_text())['started_at']<=frozen['at']:
                    raise ValueError('Query started before global freeze')
                rows=audit_native(native)
                for r in rows:
                    scores[r['condition_id']]=r['success']
                    statuses[r['condition_id']]=r['execution_status']
            elif (directory/name/'validity_failure.json').exists():
                scores={k:False for k in scores}
                failure_record=json.loads((directory/name/'validity_failure.json').read_text())
                statuses={k:failure_record.get('failure_category','PARTICIPANT_INVALID') for k in scores}
            if (native/'query_failure.json').exists():
                block['method_failures'][name+'/query']=json.loads((native/'query_failure.json').read_text())
            failure=directory/name/'method_failure.json'
            if failure.exists():
                block['method_failures'][name]=json.loads(failure.read_text())
            ap=artifact_path(directory,name)
            if ap.exists():
                retained=load_artifact(ap)
                block['retained_artifacts'][name]={'effective_artifact_hash':retained['effective_artifact_hash'],
                    'executable_fingerprint':executable_fingerprint(retained['payload']),
                    'nodes':len(retained['payload']['skill']['nodes']),'bytes':ap.stat().st_size,
                    'practice_attempts':retained['payload']['budget_used']}
            if native.exists() and not (native/'query_failure.json').exists():
                block['execution_effects'][name]=execution_chain(native,audit_native(native))
            block['scores'][name]=scores
            block['execution_statuses'][name]=statuses
        block['learning_physical_attempts']={}
        for native in [directory/n/'native' for n in ('feedback','search')]+[directory/f'test-{n}' for n in ARMS]:
            if not native.exists():
                continue
            reserved=len(list((native/'requests').glob('*.json')))
            totals['reserved_task_attempts']+=reserved
            process_file=native/'process.json'
            completed_ok=process_file.exists() and json.loads(process_file.read_text())['returncode']==0 and (native/'server_receipt.json').exists()
            if completed_ok:
                rows=audit_native(native)
            else:
                ledger=native/'episodes.jsonl'
                rows=[json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
                totals['unverified_completed_task_attempts']+=len(rows)
            totals['uncompleted_reserved_attempts']+=reserved-len(rows)
            if native.parent.name in ('feedback','search'):
                block['learning_physical_attempts'][native.parent.name]=len(rows)
            totals['native_processes']+=1
            launch_file=native/'launch.json'
            start=json.loads(launch_file.read_text())['started_at'] if launch_file.exists() else None
            finish=json.loads(process_file.read_text()).get('finished_at') if process_file.exists() else None
            if finish and start:
                totals['native_process_seconds']+=(datetime.fromisoformat(finish)-datetime.fromisoformat(start)).total_seconds()
            else:
                totals['native_processes_missing_timing']+=1
            totals['hard_boundary_episodes']+=sum(r.get('diagnostic',{}).get('hard_boundary_terminated',False) for r in rows)
            totals['position_violation_episodes']+=sum(r.get('diagnostic',{}).get('first_violation') is not None for r in rows)
            totals['limited_task_controls']+=sum(r.get('diagnostic',{}).get('target_limited_controls',0) for r in rows)
            totals['task_attempts']+=len(rows)
            totals['task_controls']+=sum(r['steps'] for r in rows)
            totals['task_physics_substeps']+=sum(r.get('diagnostic',{}).get('physics_samples',0) for r in rows)
            totals['ready_physics_substeps']+=200*len(rows)
            totals['init_invalid']+=sum(r['execution_status']=='INIT_INVALID' for r in rows)
        for name in ('designer','feedback'):
            calls=sorted((directory/name/'model_calls').glob('call-*'))
            usages=[json.loads((p/'usage.json').read_text()) for p in calls if (p/'usage.json').exists()]
            block['model_cost'][name]={'calls':len(calls),
                'input_tokens':sum(u['input_tokens'] for u in usages) if len(calls)==len(usages) else 'unknown',
                'output_tokens':sum(u['output_tokens'] for u in usages) if len(calls)==len(usages) else 'unknown',
                'known_input_tokens':sum(u['input_tokens'] for u in usages),
                'known_output_tokens':sum(u['output_tokens'] for u in usages),
                'cached_input_tokens':sum(u['cached_input_tokens'] for u in usages) if all('cached_input_tokens' in u for u in usages) and len(usages)==len(calls) else 'unknown',
                'cache_write_input_tokens':sum(u['cache_write_input_tokens'] for u in usages) if all('cache_write_input_tokens' in u for u in usages) and len(usages)==len(calls) else 'unknown',
                'wall_seconds':sum(json.loads((p/'process.json').read_text())['wall_s'] for p in calls if (p/'process.json').exists()),
                'money_cost':'unknown; no billing record'}
        blocks.append(block)
    if totals['reserved_task_attempts']>reg['physical_budget']:
        raise ValueError('Preregistered physical budget exceeded')
    result={'schema':'esl-replication-results-1','audit':('PARTIAL_WITH_MISSING_METHODS' if any(b['method_failures'] for b in blocks) else 'PASS'),'bindings':binding,'blocks':blocks,
            'summary':summarize(blocks),'physical_cost':totals}
    save_json(out/'results.json',result)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--qualification',required=True)
    p.add_argument('--gpus',default='0,1,2,3')
    p.add_argument('--query-lanes-per-gpu',type=int,choices=(1,2),default=2)
    a=p.parse_args()
    print(json.dumps(run(Path.cwd(),Path(a.output),Path(a.qualification),[int(x) for x in a.gpus.split(',')],a.query_lanes_per_gpu),indent=2))


if __name__=='__main__':
    main()
