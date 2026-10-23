"""Audit separate-policy worker confirmation, including crossed physical GPU assignment."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from physicalevobench.calibration.audit import audit_run, lines, load
from physicalevobench.calibration.statistics import paired_statistics
from physicalevobench.doctor import save_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    a=p.parse_args()
    root=Path(a.run_dir)
    cfg=load(root/'config.json')
    expected={(j['condition']['condition_id'],j['policy']):j['condition'] for j in cfg['jobs']}
    seen=set()
    rows=[]
    arms=defaultdict(lambda:{'episodes':0,'successes':0,'joint_samples':0,
                            'exposure_joint_samples':0,'any_violation_episodes':0,'max_depth_by_joint':{}})
    observations=defaultdict(dict)
    block_rows=defaultdict(list)
    for child in sorted(root.glob('block-*')):
        child_cfg=load(child/'config.json')
        block=child_cfg['block']
        policies={j['policy'] for j in child_cfg['jobs']}
        if len(policies)!=1:
            raise ValueError('Separate-policy control changed policies within a worker')
        arm=next(iter(policies))
        expected_gpu=block if arm=='original' else 1-block
        if load(child/'launch.json')['gpu']!=expected_gpu or child_cfg['gpu']!=expected_gpu:
            raise ValueError('Crossed GPU allocation mismatch')
        if child_cfg['source_commit']!=cfg['source_commit']:
            raise ValueError('Isolated workers used different registered source commits')
        audit=audit_run(child)
        summary=audit['arms'][arm]
        for key in ('episodes','successes','joint_samples','exposure_joint_samples','any_violation_episodes'):
            arms[arm][key]+=summary[key]
        for joint,depth in summary['max_depth_by_joint'].items():
            arms[arm]['max_depth_by_joint'][joint]=max(arms[arm]['max_depth_by_joint'].get(joint,0),depth)
        for row in lines(child/'episodes.jsonl'):
            key=(row['condition_id'],row['agent_id'])
            initial=load(child/row['initial_state_artifact'])
            if key in seen or expected.get(key)!=initial['condition']:
                raise ValueError('Missing/duplicate/mismatched isolated conditions')
            seen.add(key)
            observations[row['condition_id']][arm]=lines(child/row['trace_artifact'])[0]['observation']
            rows.append(row)
            block_rows[block].append(row)
    if seen!=set(expected) or len(rows)!=96:
        raise ValueError('Incomplete isolated-policy confirmation')
    matched=sum(obs['original']==obs['candidate'] for obs in observations.values())
    if matched!=48:
        raise ValueError('Separate workers did not reproduce paired initial observations')
    for summary in arms.values():
        summary['success_rate']=summary['successes']/summary['episodes']
        summary['violations_per_1000_joint_samples']=1000*summary['joint_samples']/summary['exposure_joint_samples']
    result={'status':'PASS','physical_episodes':96,'paired_conditions':48,
            'matched_initial_observation_pairs':matched,'arms':dict(arms),
            'statistics':paired_statistics(rows),
            'blocks':{str(k):paired_statistics(v) for k,v in block_rows.items()},
            'scope':'fresh conditions; separate per-policy workers and crossed GPUs; same learned model, not a new learning seed'}
    save_json(root/'audit.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
