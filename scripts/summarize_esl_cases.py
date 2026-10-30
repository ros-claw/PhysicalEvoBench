"""Post-freeze per-condition outcomes; evaluator mass never enters learner requests."""

import argparse
import csv
import json
import math
from pathlib import Path

from physicalevobench.development.place import starter_program
from physicalevobench.v02.audit import records


def read(path):
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--primary', required=True)
    p.add_argument('--extension', required=True)
    p.add_argument('--prospective', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = []
    for label, root in [('original', Path(a.primary)), ('factorial_exploratory', Path(a.extension)),
                        ('factorial_prospective', Path(a.prospective))]:
        reg = read(root/'registration.json')
        for i in range(reg['instances']):
            for method in ('frozen', 'designer', 'search', 'feedback', 'deletion'):
                worker = root/f'instance-{i}'/f'test-{method}'
                rows = [json.loads(s) for s in (worker/'episodes.jsonl').read_text().splitlines()]
                for j, row in enumerate(rows):
                    job = read(worker/'requests'/f'{j:03d}.json')
                    ep = worker/'episodes'/row['episode_id']
                    end = read(ep/'terminal_pre_reset.json')
                    trace = records(worker/row['trace_artifact'])
                    node = trace[-1]['policy_diagnostics']['decision']['program_node']
                    n = next(n for n in job['program']['nodes'] if n['id'] == node)
                    goal = job['public_goal']
                    obj = end['object_position'][0]
                    result.append({'group': label, 'learning_instance': i, 'method': method,
                                   'condition_id': row['condition_id'], 'evaluator_mass_kg': job['condition']['object_mass_kg'],
                                   'goal_x': goal[0], 'goal_y': goal[1], 'success': row['success'],
                                   'same_node_values_as_starter': job['program'] == starter_program().to_dict(),
                                   'terminal_eligible': row['place']['terminal_eligible'],
                                   'left_after_success': row['place']['left_after_first_success'],
                                   'last_command_node': node, 'last_node_guard': json.dumps(n['guard'], sort_keys=True),
                                   'terminal_xy_error_m': math.dist(obj[:2], goal[:2]),
                                   'terminal_z_error_m': abs(obj[2]-goal[2]),
                                   'terminal_object_speed_m_s': math.sqrt(sum(v*v for v in end['object_velocity'][0][:3])),
                                   'terminal_finger_min_m': min(end['finger_position']),
                                   'maximum_stable_span_s': row['place']['maximum_stable_span_s']})
    with Path(a.output).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    print(json.dumps({'query_rows': len(result), 'extra_physical_episodes': 0}))


if __name__ == '__main__':
    main()
