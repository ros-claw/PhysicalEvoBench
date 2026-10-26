"""Budgeted reference development / independently frozen confirmation."""

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.stability.audit import read, rows
from physicalevobench.stability.study import launch
from physicalevobench.v02.audit import audit_run
from physicalevobench.v02.reference import ReferenceConfig


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase',choices=['development','confirmation'],required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--batch',type=int,choices=[1,2,3],default=1)
    p.add_argument('--gpu',type=int,default=2)
    p.add_argument('--horizon',type=float,choices=[5.,10.],default=5.)
    p.add_argument('--reference-config')
    p.add_argument('--frozen-development')
    p.add_argument('--extension-reason',help='Observed reason for a separately versioned ten-second diagnostic')
    a = p.parse_args()
    root,out = Path.cwd(),Path(a.output).absolute()
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit reference source and protocol before registration')
    ref = command(['git','rev-parse','HEAD'],cwd=root)['stdout']
    source,hashes = snapshot_source(root,ref)
    configuration = asdict(ReferenceConfig(**(read(a.reference_config) if a.reference_config else {})))
    frozen = None
    if a.phase == 'confirmation':
        if not a.frozen_development:
            raise ValueError('A qualified frozen development is required')
        frozen = Path(a.frozen_development)
        from report_reference_calibration import report

        if not report(frozen)['qualified_for_confirmation']:
            raise ValueError('Development did not qualify; no confirmation physics authorized')
        registered = read(frozen/'registration.json')
        plan = registered['plans'][0]
        if plan['horizon_s'] != a.horizon or plan['reference_config'] != configuration:
            raise ValueError('Frozen controller changed before independent confirmation')
        # Reuse exact development runtime, not a newer untested controller.
        ref = registered['source_commit']
        source,hashes = snapshot_source(root,ref)
    checkpoint = '/home/dell/models/physicalevobench/franka_lift/model_1999.pt'
    model_hash = sha256(checkpoint)
    if model_hash != 'babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa':
        raise ValueError('Reference checkpoint identity changed')
    excluded = published_seeds(root)
    prior = []
    extension_evidence = []
    for file in sorted(out.parent.glob('peb-reference-*/registration.json')):
        data = read(file)
        excluded.update(registered_seed_values(data))
        prior.append({'path':str(file),'sha256':sha256(file)})
    if a.phase == 'development':
        development_budgets = sum(read(item['path'])['physical_budget'] for item in prior
                                  if read(item['path'])['phase']=='reference-development')
        if development_budgets+4 > 12:
            raise ValueError('Predeclared 12-episode development cap exhausted')
        if a.batch==1 and (a.horizon!=5. or configuration!=asdict(ReferenceConfig())):
            raise ValueError('First batch must use the preregistered default five-second controller')
        if a.horizon==10.:
            from report_reference_calibration import report

            earlier = [Path(item['path']).parent for item in prior
                       if read(item['path'])['phase']=='reference-development' and
                       read(item['path'])['plans'][0]['horizon_s']==5. and
                       (Path(item['path']).parent/'results.json').exists()]
            for path in earlier:
                result = report(path)
                verified_lift = [e['episode_id'] for e in result['episodes'] if
                                 e['termination']=='horizon' and e['steps']==250 and e['last_phase']=='lift'
                                 and not e['holding'] and any(t['transition_reason']=='object_follows_probe_not_contact_alone'
                                                             for t in e['transitions'])]
                if result['time_extension_evidence'] or verified_lift:
                    extension_evidence.append({'registration_sha256':sha256(path/'registration.json'),
                                               'diagnosis_sha256':sha256(path/'reference_diagnosis.json'),
                                               'verified_lift_timeout_episodes':verified_lift})
            if not a.extension_reason or len(a.extension_reason)<20 or not extension_evidence:
                raise ValueError('Ten-second version requires recorded five-second stage/time evidence and justification')
    rng = random.Random(2026102700+a.batch+(100 if a.phase=='confirmation' else 0))
    count = 4 if a.phase=='development' else 12
    conditions = []
    for i in range(count):
        seed = rng.randrange(2**31)
        while seed in excluded:
            seed = rng.randrange(2**31)
        excluded.add(seed)
        conditions.append({'condition_id':f'reference-{a.phase}-b{a.batch}-{i:02d}',
                           'split':a.phase,'seed':seed,'object_mass_kg':.1 if i<count/2 or count==4 else .4})
    controllers = ['StateBasedReference'] if a.phase=='development' else ['StateBasedReference','StateBasedReferenceOpen']
    plans = [{'name':c,'checkpoint_path':checkpoint,'checkpoint_sha256':model_hash,
              'policy_config_sha256':sha256(Path(checkpoint).parent/'params/agent.yaml'),
              'mode':'FixedHorizonDiagnostic','execution_layer':'TargetBounded',
              'reference_controller':c,'reference_config':configuration,
              'task_version':f'state-reference-h{a.horizon:g}-v1','horizon_s':a.horizon,
              'physical_budget':count,'jobs':[{'episode_id':f'{c}-{i:03d}','condition':condition}
                                            for i,condition in enumerate(conditions)]} for c in controllers]
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'registration.json',{'schema':'v02-diagnostics-1','phase':'reference-'+a.phase,
              'source_commit':ref,'runtime_source':str(source),'source_sha256':hashes,
              'launcher_commit':command(['git','rev-parse','HEAD'],cwd=root)['stdout'],
              'registered_at':now(),'gpu':a.gpu,'physical_budget':count*len(controllers),'plans':plans,
              'batch':a.batch,'extension_reason':a.extension_reason,
              'extension_evidence':extension_evidence,
              'hard_boundary':{'finger_depth_m':.01,'arm_depth_rad':.1},
              'target_rate_caps':{'arm_rad_s':1.,'finger_m_s':.04},'prior_registrations':prior,
              'protocol':('docs/experiments/STATE_REFERENCE_H10_PROTOCOL_20261026.md' if a.horizon==10. else
                          'docs/experiments/STATE_REFERENCE_PROTOCOL_20261026.md'),
              'frozen_development':None if frozen is None else {'path':str(frozen),'registration_sha256':sha256(frozen/'registration.json')},
              'score_role':'reference calibration; never self-evolution efficacy'})
    completed = []
    try:
        for plan in plans:
            child = out/plan['name']
            child.mkdir()
            save_json(child/'config.json',plan)
            save_json(child/'worker_reservation.json',{'episodes':count,'reserved_at':now()})
            save_json(child/'gpu_workload.json',{'at':now(),'exclusive':False,
                      'query':command(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader'])})
            launch(root,source,child,'physicalevobench.v02.collect',a.gpu)
            completed.extend({'worker':plan['name'],**r} for r in rows(child/'episodes.jsonl'))
        save_json(out/'results.json',{'episodes':completed,'count':len(completed),'learning_updates':0})
        save_json(out/'status.json',{'status':'COMPLETED','episodes':len(completed),'finished_at':now()})
        save_json(out/'audit.json',audit_run(out))
        from report_reference_calibration import report

        print(json.dumps(report(out),indent=2))
    except Exception as error:
        physical = [r for path in out.glob('*/episodes/*/upstream.jsonl') for r in rows(path) if r.get('episode_length',0)>0]
        save_json(out/'status.json',{'status':'INFRA_FAILURE','completed_physics_episodes':len(physical),
                                   'error':str(error),'at':now()})
        raise


if __name__ == '__main__':
    main()
