"""Strict learner payload shapes. This is an API boundary, not a process sandbox."""


def exact_fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('Unexpected learner payload fields')
    return value


def learner_feedback(value):
    exact_fields(value, ('observations', 'rewards', 'dones', 'time_outs'))
    exact_fields(value['observations'], ('policy', 'task_obs'))
    return value
