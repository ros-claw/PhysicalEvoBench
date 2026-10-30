"""Bounded public-state expressions for graph v2; no evaluation or state writes."""

import math

FRAMES = {'object': 'object_position', 'goal': 'task_goal_position', 'ee': 'ee_position',
          'anchor': None, 'initial_object': None}
# Scalar reductions only; arbitrary paths and evaluator state are impossible.
OBSERVABLES = {
    'finger_min': (.0, .05), 'object_speed': (0., 2.),
    'goal_xy_error': (0., 1.), 'goal_z_error': (0., 1.),
    'finger_contact_max': (0., 200.), 'finger_contact_min': (0., 200.),
    'ee_object_distance': (0., 1.), 'orientation_error': (0., 3.2),
    'object_goal_error': (0., 1.), 'target_error': (0., 1.),
}


def vector(value):
    return (isinstance(value, list) and len(value) == 3 and
            all(type(x) in (int, float) and math.isfinite(x) and abs(x) <= .2 for x in value))


def validate_target(value):
    if (not isinstance(value, dict) or set(value) != {'frame', 'offset_m', 'grasp_offset'} or
            value['frame'] not in FRAMES or not vector(value['offset_m']) or
            type(value['grasp_offset']) is not bool):
        raise ValueError('Bounded public relative target required')


def validate_guard(value, depth=0):
    if depth > 3 or not isinstance(value, dict):
        raise ValueError('Bounded guard expression required')
    if set(value) in ({'all'}, {'any'}):
        children = next(iter(value.values()))
        if not isinstance(children, list) or not 1 <= len(children) <= 4:
            raise ValueError('One to four public guards required')
        for child in children:
            validate_guard(child, depth+1)
    elif set(value) == {'observable', 'op', 'value'}:
        key, number = value['observable'], value['value']
        if (key not in OBSERVABLES or value['op'] not in ('le', 'ge') or
                type(number) not in (int, float) or not math.isfinite(number) or
                not OBSERVABLES[key][0] <= number <= OBSERVABLES[key][1]):
            raise ValueError('Unknown or out-of-range public comparison')
    else:
        raise ValueError('Unknown public guard fields')


def evaluate(value, obs, target):
    if 'all' in value:
        return all(evaluate(c, obs, target) for c in value['all'])
    if 'any' in value:
        return any(evaluate(c, obs, target) for c in value['any'])
    goal = obs['task_goal_position']
    obj = obs['object_position']
    numbers = {
        'finger_min': min(obs['finger_position']),
        'object_speed': math.sqrt(sum(x*x for x in obs['object_velocity'])),
        'goal_xy_error': math.dist(obj[:2], goal[:2]), 'goal_z_error': abs(obj[2]-goal[2]),
        'finger_contact_min': min(obs['cube_contact_force']),
        'finger_contact_max': max(obs['cube_contact_force']),
        'ee_object_distance': math.dist(obs['ee_position'], obj),
        'orientation_error': obs['orientation_error'],
        'object_goal_error': math.dist(obj, goal),
        'target_error': math.dist(obs['ee_position'], target),
    }
    number = numbers[value['observable']]
    return number <= value['value'] if value['op'] == 'le' else number >= value['value']


def comparison(name, op, number):
    return {'observable': name, 'op': op, 'value': number}


def relative(frame, dz=0., grasp=True):
    return {'frame': frame, 'offset_m': [0., 0., dz], 'grasp_offset': grasp}
