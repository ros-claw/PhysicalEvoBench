"""Small registered, no-approach slot/condition crossover, separate from learning."""

import argparse
import concurrent.futures
import json
from pathlib import Path

from physicalevobench.core.pilot import worker_config
from physicalevobench.core.runtime import NativeSession
from physicalevobench.doctor import command,save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.audit import records
from physicalevobench.v02.reference_artifact import load

CASES=[{'label':'A-extension-early-drop','seed':315924514,'object_mass_kg':.1,'public_goal':[.60,.12,.021]},
       {'label':'B-fresh-early-drop','seed':903479326,'object_mass_kg':.1,'public_goal':[.60,.12,.021]},
       {'label':'N-preselected-normal-light','seed':1132640734,'object_mass_kg':.1,'public_goal':[.62,-.12,.021]}]


def run(root,out,recover=None):
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit diagnostic source before reservation')
    source=command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    cfg=worker_config(load(root/'configs/core/frozen_reference.json'),3)
    cfg.update(core_task='initialization_diagnostic',task_version='esl-initialization-diagnostic-v1',
               horizon_s=1.,control_profile='contact-integral-v1')
    batches=[{'id':f'observe-{int(observed)}-order-{start}','instrumented':observed,
              'cases':[CASES[(start+j)%3] for j in range(3)],'gpu':[0,2][(start+int(observed))%2]}
              for observed in (False,True) for start in range(3)]
    recovered=None
    if recover:
        from physicalevobench.doctor import sha256
        old=json.loads((recover/'registration.json').read_text())
        missing=[]
        for batch in old['batches']:
            native=recover/batch['id']
            if not (native/'launch.json').exists():
                missing.append(batch)
            elif not (native/'process.json').exists() or json.loads((native/'process.json').read_text())['returncode']!=0:
                raise ValueError('Recovery only allows attempts that never launched physics')
        batches=missing
        recovered={'path':str(recover),'registration_sha256':sha256(recover/'registration.json'),
                   'rule':'Only previously unlaunched batches; preserve every completed outcome'}
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'registration.json',{'schema':'esl-initialization-crossover-1','at':now(),
              'source_commit':source,'mode':'DEV_DIAGNOSTIC','physical_budget':3*len(batches),'recovery':recovered,
              'resource_ceiling':48,'batches':batches,'cfg':cfg,
              'hypotheses':['condition vs first process slot','instrumentation readback may change readiness timing'],
              'rules':'All cases retained; fixed hold, no approach; no reseeding/retries; three Latin-square orders per instrumentation state. Does not establish a learning effect.'})
    save_json(out/'status.json',{'status':'RUNNING'})
    def one(batch):
        session=NativeSession(root,out/batch['id'],source,{**cfg,'initialization_diagnostic':batch['instrumented']},batch['gpu'])
        try:
            session.ready()
            for slot,c in enumerate(batch['cases']):
                session.trial({'episode_id':f'slot-{slot}','condition':{'condition_id':c['label'],
                    'split':'diagnosis','seed':c['seed'],'object_mass_kg':c['object_mass_kg']},
                    'reference_config':cfg['reference_config'],'diagnostic_hold':True,
                    'identity':{'slot':slot,'label':c['label'],'instrumented':batch['instrumented']}})
        finally:
            session.close()
    # One native process per selected shared GPU; never touch unrelated sessions.
    def gpu_group(gpu):
        for batch in batches:
            if batch['gpu']==gpu:
                one(batch)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(gpu_group,[0,2]))
    result=summarize(out)
    save_json(out/'status.json',{'status':'COMPLETED','at':now(),'physical_episodes':len(result['episodes'])})
    return result


def summarize(out):
    reg=json.loads((out/'registration.json').read_text())
    result=[]
    for batch in reg['batches']:
        native=out/batch['id']
        if json.loads((native/'process.json').read_text())['returncode']!=0:
            raise ValueError('Native diagnostic process failed')
        for slot,case in enumerate(batch['cases']):
            ep=native/'episodes'/f'slot-{slot}'
            frames=records(ep/'physics.jsonl.gz')
            row=json.loads((ep/'episode.json').read_text())
            trace=records(ep/'trace.jsonl.gz')
            z=[f['object_position'][0][2] for f in frames]
            result.append({'batch':batch['id'],'slot':slot,'label':case['label'],
                'instrumented':batch['instrumented'],'steps':row['steps'],
                'minimum_object_z_m':min(z),'terminal_object_z_m':z[-1],
                'terminal_velocity':frames[-1]['object_velocity'][0],
                'unsupported_drop_observed':min(z)<-.01,
                'all_commands_hold':all(t['policy_diagnostics']['diagnostic_control']=='fixed_initial_joint_target_open_gripper' for t in trace),
                'support_contact':'not_measured','runtime_shape':'see initialization_runtime.json if instrumented'})
    value={'schema':'esl-initialization-crossover-results-1','episodes':result,
           'physical_episodes':len(result),'unsupported_drops':sum(r['unsupported_drop_observed'] for r in result),
           'scope':'Small diagnostic, not independent learning; observed readback is a possible intervention'}
    save_json(out/'results.json',value)
    return value


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--recover',type=Path)
    a=p.parse_args()
    print(json.dumps(run(Path.cwd(),Path(a.output),a.recover),indent=2))


if __name__=='__main__':
    main()
