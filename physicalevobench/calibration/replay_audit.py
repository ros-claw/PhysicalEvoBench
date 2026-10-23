"""Compare same-worker repeats with fresh-process replays of registered conditions."""

import argparse
from pathlib import Path

from physicalevobench.calibration.audit import audit_run, lines, load
from physicalevobench.doctor import save_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--persistent',required=True)
    p.add_argument('--fresh',required=True)
    a=p.parse_args()
    persistent,fresh=Path(a.persistent),Path(a.fresh)
    audit_run(persistent)
    cfg=load(persistent/'config.json')
    fresh_cfg=load(fresh/'config.json')
    children=sorted(fresh.glob('fresh-*'))
    if len(children)!=len(fresh_cfg['jobs']) or len(load(fresh/'budget_ledger.json'))!=len(children):
        raise ValueError('Fresh-process budget or completeness mismatch')
    results=[]
    for child in children:
        audit_run(child)
        row=lines(child/'episodes.jsonl')[0]
        original=[r for r in lines(persistent/'episodes.jsonl') if r['condition_id']==row['condition_id']]
        if len(original)!=3:
            raise ValueError('Need three registered persistent replays')
        fresh_initial=load(child/row['initial_state_artifact'])
        traces=[lines(persistent/r['trace_artifact']) for r in original]
        new_trace=lines(child/row['trace_artifact'])
        first=traces[0][0]
        new=new_trace[0]
        initial=load(persistent/original[0]['initial_state_artifact'])
        if fresh_initial['condition']!=initial['condition']:
            raise ValueError('Fresh process condition differs from persistent study')
        results.append({'condition_id':row['condition_id'], 'seed':row['seed'],
            'mass':fresh_initial['mass_readback_kg'][0][0],
            'persistent_successes':[r['success'] for r in original], 'fresh_success':row['success'],
            'initial_states_equal':fresh_initial==initial,
            'initial_observations_equal':new['observation']==first['observation'],
            'initial_joint_velocities_equal':new['joint_velocity']==first['joint_velocity'],
            'first_actions_equal':new['applied_action']==first['applied_action'],
            'within_worker_exact_trajectories':all(t==traces[0] for t in traces[1:]),
            'fresh_exact_trajectory':new_trace==traces[0]})
    if {r['condition_id'] for r in results}!={j['condition']['condition_id'] for j in cfg['jobs']}:
        raise ValueError('Fresh/persistent coverage mismatch')
    save_json(fresh/'audit.json',{'status':'PASS','physical_episodes':len(children),
        'paired_conditions':len(results), 'comparison':results,
        'within_worker_discordant_conditions':sum(len(set(r['persistent_successes']))>1 for r in results),
        'fresh_vs_first_discordant_conditions':sum(r['fresh_success']!=r['persistent_successes'][0] for r in results),
        'scope':'reset/process diagnostics; no equivalence or unique GPU-causality claim'})


if __name__=='__main__':
    main()
