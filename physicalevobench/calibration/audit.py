"""Recompute diagnostic outcomes from raw physical traces, never stored scores alone."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from physicalevobench.doctor import save_json


def load(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def audit_run(out):
    out = Path(out)
    cfg = load(out/'config.json')
    ledger = load(out/'budget_ledger.json')
    rows = lines(out/'episodes.jsonl')
    if len(rows) != len(cfg['jobs']) or len(rows) != len(ledger) or len(rows) > cfg['physical_budget']:
        raise ValueError('Incomplete or over-budget physical study')
    summaries = defaultdict(lambda: {'episodes':0, 'successes':0, 'joint_samples':0,
                                     'exposure_joint_samples':0, 'any_violation_episodes':0,
                                     'max_depth_by_joint':{}})
    conditions = defaultdict(list)
    for job, reservation, row in zip(cfg['jobs'], ledger, rows, strict=True):
        eid = job['episode_id']
        if row['episode_id'] != eid or reservation['episode_id'] != eid:
            raise ValueError('Job/reservation/episode order mismatch')
        episode = out/'episodes'/eid
        if load(episode/'episode.json') != row:
            raise ValueError('Episode index differs from physical artifact')
        initial = load(episode/'initial_state.json')
        if initial['condition'] != job['condition']:
            raise ValueError('Physical initial condition differs from registration')
        if abs(initial['mass_readback_kg'][0][0]-job['condition']['object_mass_kg']) > 1e-6:
            raise ValueError('Physical mass readback mismatch')
        trace = lines(episode/'trace.jsonl')
        official = [r for r in lines(episode/'upstream.jsonl') if r.get('episode_length',0)>0]
        if len(official)!=1 or official[0]['episode_length'] != len(trace) or row['steps'] != len(trace):
            raise ValueError('Official completion and action trace mismatch')
        if official[0]['success'] != row['success'] or type(row['success']) is not bool:
            raise ValueError('Official success differs from stored score')
        count = 0
        depths = [[] for _ in initial['joint_limits'][0]]
        for i, sample in enumerate(trace):
            if sample['step'] != i or sample['raw_action'] != sample['applied_action']:
                raise ValueError('Expected consecutive identity-skill calibration actions')
            if not all(math.isfinite(x) for x in sample['applied_action'][0]):
                raise ValueError('Nonfinite action')
            if job['policy']=='open_gripper' and sample['applied_action'][0][7] != 1:
                raise ValueError('Known degraded policy did not keep gripper open')
            for j,(q,(low,high)) in enumerate(zip(sample['joint_position'][0], initial['joint_limits'][0], strict=True)):
                depth = max(low-q, q-high, 0.)
                depths[j].append(depth)
                count += q < low-.001 or q > high+.001
        if count != row['joint_limit_violation_count']:
            raise ValueError('Historical sampled safety count differs from raw positions')
        safety = load(episode/'sampled_safety.json')
        if safety['violation_joint_samples'] != count or safety['samples'] != len(trace):
            raise ValueError('Sampled safety exposure mismatch')
        for j,item in enumerate(safety['per_joint']):
            if abs(item['maximum_depth']-max(depths[j])) > 1e-10:
                raise ValueError('Safety maximum depth mismatch')
            if abs(item['integrated_depth_coordinate_seconds']-sum(depths[j])*safety['step_dt']) > 1e-10:
                raise ValueError('Safety integrated depth mismatch')
        arm = summaries[job['policy']]
        arm['episodes'] += 1
        arm['successes'] += int(row['success'])
        arm['joint_samples'] += count
        arm['exposure_joint_samples'] += len(trace)*len(depths)
        arm['any_violation_episodes'] += int(count>0)
        for item in safety['per_joint']:
            arm['max_depth_by_joint'][item['joint']] = max(arm['max_depth_by_joint'].get(item['joint'],0),item['maximum_depth'])
        conditions[row['condition_id']].append({'policy':job['policy'], 'success':row['success'],
            'initial_observation':trace[0]['observation'], 'first_action':trace[0]['applied_action'],
            'initial_joint_velocity':trace[0]['joint_velocity'], 'initial_state':initial})
    for summary in summaries.values():
        summary['success_rate'] = summary['successes']/summary['episodes']
        summary['violations_per_1000_joint_samples'] = 1000*summary['joint_samples']/summary['exposure_joint_samples']
    paired = {}
    if all(sum(x['policy']=='original' for x in group)==1 and len(group)==2 for group in conditions.values()):
        wins=losses=0
        for group in conditions.values():
            old=next(x for x in group if x['policy']=='original')
            new=next(x for x in group if x['policy']!='original')
            wins += new['success'] and not old['success']
            losses += old['success'] and not new['success']
        n=wins+losses
        p=sum(math.comb(n,k) for k in range(wins,n+1))/2**n if n else 1.
        paired={'candidate_only_success':wins,'original_only_success':losses,'one_sided_exact_p':p}
    replay=[]
    for cid,group in conditions.items():
        same=[x for x in group if x['policy']=='original']
        if len(same)>1:
            first=same[0]
            replay.append({'condition_id':cid,'successes':[x['success'] for x in same],
                           'initial_observations_equal':all(x['initial_observation']==first['initial_observation'] for x in same),
                           'initial_joint_velocities_equal':all(x['initial_joint_velocity']==first['initial_joint_velocity'] for x in same),
                           'first_actions_equal':all(x['first_action']==first['first_action'] for x in same)})
    result={'status':'PASS','physical_episodes':len(rows),'mode':cfg['mode'],
            'arms':dict(summaries),'paired':paired,'replay':replay,
            'scope':'physical trace integrity; scientific efficacy is a separate decision'}
    if cfg['mode']=='measurement':
        gain=summaries['original']['success_rate']-summaries['open_gripper']['success_rate']
        result['measurement_control']={'success_rate_difference':gain,'pass':gain>=.5}
    save_json(out/'audit.json',result)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    a=p.parse_args()
    print(json.dumps(audit_run(a.run_dir),indent=2))


if __name__=='__main__':
    main()
