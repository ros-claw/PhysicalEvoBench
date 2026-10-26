"""Four preregistered parameter-activation episodes, not Agent learning."""

import argparse
import json
import random
import shutil
from pathlib import Path

from report_reference_calibration import report as reference_report

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.stability.audit import read, rows
from physicalevobench.stability.study import launch
from physicalevobench.v02.audit import audit_run, records
from physicalevobench.v02.reference import ReferenceConfig, ReferenceFSM
from physicalevobench.v02.reference_artifact import ReferenceSkill, digest, load


def report(directory):
    directory = Path(directory)
    audit = audit_run(directory)
    reg = read(directory/'registration.json')
    base = load(directory/'baseline_reference.json')
    if sha256(directory/'baseline_reference.json')!=reg['baseline_reference_file_sha256']:
        raise ValueError('Parameter baseline artifact changed')
    data = {}
    for plan in reg['plans']:
        skill = ReferenceSkill.from_dict(plan['reference_skill'])
        if skill.configuration(base)!=plan['reference_config'] or plan['source_commit']!=base['source_commit']:
            raise ValueError('Parameter worker differs from its executable skill')
        worker = directory/plan['name']
        row = rows(worker/'episodes.jsonl')[0]
        episode = worker/'episodes'/row['episode_id']
        data[plan['name']] = {'plan':plan,'row':row,'initial':read(episode/'initial_state.json'),
                             'trace':records(episode/'trace.jsonl.gz'),
                             'controls':records(episode/'controls.jsonl.gz')}
    baseline = data['baseline']
    pairs = {}
    for name in ('identity','clearance','close_wait'):
        other = data[name]
        if baseline['initial']!=other['initial']:
            raise ValueError('Parameter comparison initial physical state differs')
        fsms = [ReferenceFSM(ReferenceConfig(**item['plan']['reference_config'])) for item in (baseline,other)]
        command_difference = None
        for sample in baseline['trace']:
            decisions = [fsm.update(sample['policy_diagnostics']['public'],.02) for fsm in fsms]
            if any(decisions[0][key]!=decisions[1][key] for key in ('phase','target_position','gripper')):
                command_difference = sample['step']
                break
        actual_differences = [i for i,(a,b) in enumerate(zip(baseline['controls'],other['controls'],strict=True))
                              if max(abs(x-y) for x,y in zip(a['applied_target'],b['applied_target'],strict=True))>1e-5]
        activation = next((i for i in actual_differences if command_difference is not None and i>=command_difference),None)
        metric = other['row']['diagnostic']
        pairs[name] = {'skill_sha256':ReferenceSkill.from_dict(other['plan']['reference_skill']).sha256,
                       'initial_physical_state_equal':True,'first_same_input_command_difference_step':command_difference,
                       'first_actual_target_difference_step':actual_differences[0] if actual_differences else None,
                       'actual_target_difference_after_command_step':activation,
                       'parameter_active':command_difference is not None and activation is not None,
                       'holding':metric['holding']['stable_success'],'holding_span_s':metric['holding']['maximum_holding_span_s'],
                       'any_violation':metric['first_violation'] is not None}
    if pairs['identity']['skill_sha256']!=ReferenceSkill.from_dict(baseline['plan']['reference_skill']).sha256:
        raise ValueError('Identity created a different candidate')
    result = {'schema':'reference-parameter-effects-1','audit':audit,'pairs':pairs,
              'both_parameters_active':all(pairs[n]['parameter_active'] for n in ('clearance','close_wait')),
              'scope':'One selected condition plus identity replay. Activation, not efficacy or uncertainty calibration. Same-input guard replay is counterfactual, live applied targets are measured.'}
    save_json(directory/'parameter_effects.json',result)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--confirmation',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--gpu',type=int,default=2)
    a=p.parse_args()
    root,out,confirmation=Path.cwd(),Path(a.output).absolute(),Path(a.confirmation)
    if command(['git','status','--porcelain'],cwd=root)['stdout']:
        raise ValueError('Commit parameter protocol before physical registration')
    if not reference_report(confirmation)['reference_gate_passed']:
        raise ValueError('Positive reference confirmation must pass before parameter activation trials')
    base=load(confirmation/'frozen_reference.json')
    source,hashes=snapshot_source(root,base['source_commit'])
    excluded=published_seeds(root)
    development=0
    for file in out.parent.glob('peb-reference-*/registration.json'):
        value=read(file)
        excluded.update(registered_seed_values(value))
        if value['phase'] in ('reference-development','reference-parameter-effects'):
            development+=value['physical_budget']
    if development+4>12:
        raise ValueError('Total development cap includes parameter trials')
    rng=random.Random(2026102605)
    seed=rng.randrange(2**31)
    while seed in excluded:
        seed=rng.randrange(2**31)
    condition={'condition_id':'reference-parameter-effect-00','seed':seed,'split':'development','object_mass_kg':.1}
    original=read(confirmation/'registration.json')['plans'][0]
    plans=[]
    for name,params in [('baseline',{}),('identity',{}),('clearance',{'approach_clearance_m':.12}),('close_wait',{'minimum_close_s':.7})]:
        skill=ReferenceSkill(digest(base),**params)
        plans.append({**original,'name':name,'source_commit':base['source_commit'],'reference_skill':skill.to_dict(),
                      'reference_config':skill.configuration(base),'physical_budget':1,
                      'jobs':[{'episode_id':name+'-000','condition':condition}]})
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(confirmation/'frozen_reference.json',out/'baseline_reference.json')
    save_json(out/'registration.json',{'schema':'v02-diagnostics-1','phase':'reference-parameter-effects',
              'source_commit':base['source_commit'],'source_sha256':hashes,'runtime_source':str(source),
              'launcher_commit':command(['git','rev-parse','HEAD'],cwd=root)['stdout'],
              'registered_at':now(),'gpu':a.gpu,'physical_budget':4,'plans':plans,
              'hard_boundary':{'finger_depth_m':.01,'arm_depth_rad':.1},'target_rate_caps':{'arm_rad_s':1.,'finger_m_s':.04},
              'baseline_reference_file_sha256':sha256(out/'baseline_reference.json'),
              'protocol':'docs/experiments/REFERENCE_PARAMETER_EFFECT_PROTOCOL_20261026.md',
              'score_role':'parameter activation only; actual repeated episodes all counted'})
    complete=[]
    try:
        for plan in plans:
            child=out/plan['name']
            child.mkdir()
            save_json(child/'config.json',plan)
            save_json(child/'worker_reservation.json',{'episodes':1,'reserved_at':now()})
            save_json(child/'gpu_workload.json',{'exclusive':False,'at':now(),
                      'query':command(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader'])})
            launch(root,source,child,'physicalevobench.v02.collect',a.gpu)
            complete.extend({'worker':plan['name'],**row} for row in rows(child/'episodes.jsonl'))
        save_json(out/'results.json',{'episodes':complete,'count':len(complete),'learning_updates':0})
        save_json(out/'status.json',{'status':'COMPLETED','episodes':len(complete),'finished_at':now()})
        print(json.dumps(report(out),indent=2))
    except Exception as error:
        physical=[r for path in out.glob('*/episodes/*/upstream.jsonl') for r in rows(path) if r.get('episode_length',0)>0]
        save_json(out/'status.json',{'status':'INFRA_FAILURE','completed_physics_episodes':len(physical),'error':str(error),'at':now()})
        raise


if __name__=='__main__':
    main()
