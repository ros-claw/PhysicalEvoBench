"""Inspect old anomalies without rescoring them or spending more physics."""

import argparse
import json
from pathlib import Path

from physicalevobench.doctor import save_json,sha256
from physicalevobench.v02.audit import records

CASES=[('/home/dell/peb-esl-extension-20261030-001/instance-0','frozen','designer'),
       ('/home/dell/peb-esl-extension-20261030-001/instance-0','search','designer'),
       ('/home/dell/peb-esl-external-runs-20261030/peb-learning-001/instance-0','feedback','frozen')]


def summarize(out):
    results=[]
    for root,abnormal,normal in CASES:
        a=Path(root)/f'test-{abnormal}'/'episodes/query-000'
        b=Path(root)/f'test-{normal}'/'episodes/query-000'
        af,bf=records(a/'physics.jsonl.gz'),records(b/'physics.jsonl.gz')
        at,bt=records(a/'trace.jsonl.gz'),records(b/'trace.jsonl.gz')
        ai,bi=[json.loads((p/'initial_state.json').read_text()) for p in (a,b)]
        if ai['condition']!=bi['condition']:
            raise ValueError('Old diagnostic comparison has different registered condition')
        steps=[]
        for i,(x,y) in enumerate(zip(af,bf)):
            az,bz=x['object_position'][0][2],y['object_position'][0][2]
            av,bv=x['object_velocity'][0][2],y['object_velocity'][0][2]
            if abs(az-bz)>.001 or abs(av-bv)>.05:
                steps.append({'substep_index':i,'time_after_first_physics_s':(i+1)*.005,
                              'abnormal_z_m':az,'normal_z_m':bz,'abnormal_vz_m_s':av,'normal_vz_m_s':bv})
        if not steps:
            raise ValueError('No divergence found in old designated anomaly')
        first=steps[0]
        index=first['substep_index']//4
        commands=[]
        for label,trace in [('abnormal',at),('preselected_normal',bt)]:
            d=trace[min(index,len(trace)-1)]['policy_diagnostics']
            commands.append({'case':label,'decision':d['decision'],
                             'ee_object_distance_m':sum((x-y)**2 for x,y in zip(d['public']['ee_position'],d['public']['object_position'],strict=True))**.5,
                             'measured_finger_cube_normal_N':d['public']['cube_contact_force']})
        results.append({'abnormal':str(a),'preselected_control':str(b),'condition':ai['condition'],
            'initial_conditions_equal':ai['condition']==bi['condition'],
            'first_divergence_rule':'Earliest recorded post-physics substep with |dz|>.001m or |dvz|>.05m/s; exploratory diagnostic threshold, not a success rule',
            'first_divergence':first,'commands_at_divergence':commands,
            'raw_hashes':{str(p):sha256(p) for p in (a/'physics.jsonl.gz',b/'physics.jsonl.gz',a/'trace.jsonl.gz',b/'trace.jsonl.gz')},
            'cube_table_pair_contact':'not_measured in old protocol; cannot identify exact collider/cooking cause retrospectively'})
    result={'schema':'esl-old-early-drop-diagnostic-1','cases':results,
            'scope':'Historical task failures retained. First divergence is a physical observation, not unique root cause or new learning evidence.'}
    save_json(out,result)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    a=p.parse_args()
    print(json.dumps(summarize(Path(a.output)),indent=2))


if __name__=='__main__':
    main()
