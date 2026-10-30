"""Align measured release events; missing support contact remains not_measured."""

import argparse
import csv
import json
import math
from pathlib import Path

from physicalevobench.doctor import save_json
from physicalevobench.v02.audit import records


def aligned(directory):
    root = Path(directory)
    rows = [json.loads(s) for s in (root/'native/episodes.jsonl').read_text().splitlines()]
    result = []
    timelines = []
    for row in rows:
        ep = root/'native/episodes'/row['episode_id']
        trace = records(ep/'trace.jsonl.gz')
        controls = records(ep/'controls.jsonl.gz')
        goal = row.get('place', {}).get('place_target_world')
        if goal is None:
            continue
        opening = next((i for i, t in enumerate(trace) if
                        t['policy_diagnostics']['decision']['gripper'] == 'open' and
                        t['policy_diagnostics']['decision'].get('program_node') == 'release'), None)
        if opening is None:
            result.append({'episode': row['episode_id'], 'opening': 'not_reached'})
            continue
        events = {'opening_command': opening, 'support_contact': 'not_measured'}
        previous = [i for i in range(opening) if min(trace[i]['policy_diagnostics']['public']['cube_contact_force']) >= .5]
        events['last_bilateral_before_open'] = previous[-1] if previous else None
        for name, predicate in {
            'actual_open_035': lambda p: min(p['finger_position']) >= .035,
            'finger_contact_lost': lambda p: max(p['cube_contact_force']) <= .5,
            'geometry_near_plane': lambda p: abs(p['object_position'][2]-.021) <= .005,
            'low_speed': lambda p: math.sqrt(sum(v*v for v in p['object_velocity'])) <= .1,
        }.items():
            events[name] = next((i for i in range(opening, len(trace)) if
                                 predicate(trace[i]['policy_diagnostics']['public'])), None)
        events['retreat_command'] = next((i for i in range(opening, len(trace)) if
                                         trace[i]['policy_diagnostics']['decision'].get('program_node') == 'retreat'), None)
        events['speed_peak'] = max(range(opening, len(trace)), key=lambda i: math.sqrt(sum(
            v*v for v in trace[i]['policy_diagnostics']['public']['object_velocity'])))
        details = {}
        for name, i in events.items():
            if not isinstance(i, int):
                details[name] = i
                continue
            p = trace[i]['policy_diagnostics']['public']
            details[name] = {'step': i, 'time_s': i*.02,
                             'goal_xy_error_m': math.dist(p['object_position'][:2], goal[:2]),
                             'object_speed_m_s': math.sqrt(sum(v*v for v in p['object_velocity'])),
                             'finger_position_m': p['finger_position'],
                             'finger_normal_force_n': p['cube_contact_force']}
        result.append({'episode': row['episode_id'], 'success': row['success'], 'events': details})
        for i in range(max(0, opening-30), min(len(trace), opening+180)):
            p = trace[i]['policy_diagnostics']['public']
            d = trace[i]['policy_diagnostics']
            c = controls[i]
            timelines.append({'episode': row['episode_id'], 'step': i, 'relative_time_s': (i-opening)*.02,
                              'object_position': json.dumps(p['object_position']),
                              'ee_position': json.dumps(p['ee_position']),
                              'object_velocity': json.dumps(p['object_velocity']),
                              'grasp_offset': json.dumps([a-b for a, b in zip(p['ee_position'], p['object_position'], strict=True)]),
                              'finger_position': json.dumps(p['finger_position']),
                              'normal_force': json.dumps(p['cube_contact_force']),
                              'raw_target': json.dumps(d['target_position']),
                              'processed_joint_target': json.dumps(c['processed_target']),
                              'applied_joint_target': json.dumps(c['applied_target']),
                              'integral_bias': json.dumps(d['bounded_joint_integral_rad']),
                              'limited_joints': json.dumps(c['limited_joints'])})
    return {'schema': 'release-event-alignment-1', 'episodes': result,
            'scope': 'Measured associations, not unique causal identification; support contact not_measured'}, timelines


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result, timelines = aligned(a.run_dir)
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    save_json(out/'events.json', result)
    if timelines:
        with (out/'timeline.csv').open('w') as f:
            writer = csv.DictWriter(f, fieldnames=list(timelines[0]))
            writer.writeheader()
            writer.writerows(timelines)


if __name__ == '__main__':
    main()
