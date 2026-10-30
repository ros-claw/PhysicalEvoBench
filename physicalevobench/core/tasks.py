"""Independent task lifecycle; regression remains runnable without learning qualification."""

TASKS = {
    'lift-regression': {'status': 'REGRESSION', 'task_version': 'state-reference-h10-v1',
                        'scope': 'Physical execution smoke/retention; saturated, not learning-qualified'},
    'place-settle-ready': {'status':'DEV','task_version':'core-place-public-v5-ready2',
                           'scope':'State-only Ready2 finite problem; current content-bound physical qualification required'},
    'place-settle': {'status': 'DEV', 'task_version': 'core-place-public-v3-dev',
                     'scope': 'Public-goal release engineering; qualification required'},
}


def task(name, mode):
    if name not in TASKS:
        raise ValueError(f'Invalid task {name}; choose from {list(TASKS)}')
    if mode not in ('DEV', 'QUALIFICATION', 'BENCHMARK'):
        raise ValueError('Invalid execution mode')
    value = dict(TASKS[name])
    if name=='place-settle-ready':
        from pathlib import Path
        receipt=Path('configs/reliability/qualification.json')
        if receipt.exists():
            from physicalevobench.core.replication import validate_contract
            try:
                validate_contract(Path.cwd(),receipt)
                value.update(status='QUALIFIED',qualification_receipt=str(receipt))
            except (ValueError,KeyError):
                value['qualification_status']='STALE_OR_INVALID'
    if name=='place-settle':
        import json
        from pathlib import Path
        receipt=Path('configs/learning/qualification.json')
        if receipt.exists():
            q=json.loads(receipt.read_text())
            if q.get('status')=='QUALIFIED':
                from physicalevobench.core.execution_identity import validate_execution
                from physicalevobench.v02.reference_artifact import load
                try:
                    validate_execution(Path.cwd(),q,load(Path('configs/core/frozen_reference.json')))
                    value.update(status='QUALIFIED',qualification_receipt=str(receipt),
                                 scope='Historical finite release pilot; not Ready2 results')
                except (ValueError,KeyError,FileNotFoundError):
                    value['qualification_status']='STALE_OR_DIFFERENT_EXECUTION'
    if mode == 'BENCHMARK' and value['status'] != 'QUALIFIED':
        raise ValueError(f'Task {name} is {value["status"]}; cannot receive formal scores')
    return value
