"""Independent task lifecycle; regression remains runnable without learning qualification."""

TASKS = {
    'lift-regression': {'status': 'REGRESSION', 'task_version': 'state-reference-h10-v1',
                        'scope': 'Physical execution smoke/retention; saturated, not learning-qualified'},
    'place-settle': {'status': 'DEV', 'task_version': 'core-place-public-v3-dev',
                     'scope': 'Public-goal release engineering; qualification required'},
}


def task(name, mode):
    if name not in TASKS:
        raise ValueError(f'Invalid task {name}; choose from {list(TASKS)}')
    if mode not in ('DEV', 'QUALIFICATION', 'BENCHMARK'):
        raise ValueError('Invalid execution mode')
    value = dict(TASKS[name])
    if mode == 'BENCHMARK' and value['status'] != 'QUALIFIED':
        raise ValueError(f'Task {name} is {value["status"]}; cannot receive formal scores')
    return value
