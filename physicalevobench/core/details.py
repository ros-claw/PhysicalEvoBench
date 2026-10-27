"""Additive development failure observations, never retrospective score changes."""

import json
import math
from pathlib import Path

from physicalevobench.doctor import save_json
from physicalevobench.v02.audit import records


def release_details(root,write=True):
    root=Path(root)
    reg=json.loads((root/'registration.json').read_text())
    data=[]
    rows=[json.loads(x) for x in (root/'native/episodes.jsonl').read_text().splitlines()]
    for row,job in zip(rows,reg['jobs'],strict=True):
        if job['force_open']:
            continue
        ep=root/'native/episodes'/row['episode_id']
        trace=records(ep/'trace.jsonl.gz')
        target=row['place']['place_target_world']
        release=next((s for s in trace if s['policy_diagnostics']['decision'].get('program_node')=='release'),None)
        terminal=json.loads((ep/'terminal_pre_reset.json').read_text())
        obj=terminal['object_position'][0]
        item={'episode_id':row['episode_id'],'mass_kg':job['condition']['object_mass_kg'],'success':row['success'],
              'terminal_horizontal_error_m':math.dist(obj[:2],target[:2]),'terminal_object_position':obj,
              'terminal_fingers':terminal['finger_position'],'lift_observed':row['place']['lift_observed'],
              'transport_observed':row['place']['transport_observed'],
              'last_node':trace[-1]['policy_diagnostics']['decision'].get('program_node')}
        if release:
            k=release['step']
            before,at=trace[k-1]['policy_diagnostics'],release['policy_diagnostics']
            item.update(release_step=k,release_target_error_m=math.dist(release['object_position'][0][:2],target[:2]),
                        integral_before=before['bounded_joint_integral_rad'],integral_at=at['bounded_joint_integral_rad'],
                        opening_to_terminal_horizontal_displacement_m=math.dist(obj[:2],release['object_position'][0][:2]))
        data.append(item)
    result={'schema':'core-place-release-diagnosis-1','episodes':data,
            'scope':'Additive development observation; no changed score, no additional trials, no unique-cause inference.'}
    if write:
        save_json(root/'release_diagnosis.json',result)
    return result
