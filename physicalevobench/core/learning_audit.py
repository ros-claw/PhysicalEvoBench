"""Bind model decisions, persisted artifacts and paired physical execution."""

import json
import math
from pathlib import Path

from physicalevobench.core.artifact import load
from physicalevobench.core.program import Program
from physicalevobench.doctor import sha256
from physicalevobench.v02.reference_artifact import digest


def read(path):
    return json.loads(Path(path).read_text())


def flat(value):
    return [x for item in value for x in (flat(item) if isinstance(item, list) else [item])]


def initial_for_pair(directory):
    initial=read(directory/'initial_capture.json')
    state=read(directory/'initial_state.json')
    for field in ('mass_readback_kg','inertia_readback','object_orientation','joint_limits'):
        initial[field]=state[field]
    return initial


def assert_initial_pair(a, b):
    fields=('joint_position','object_position','target_command','joint_velocity','object_velocity',
            'finger_position','ee_position_world','mass_readback_kg','inertia_readback',
            'object_orientation','joint_limits')
    for field in fields:
        if field not in a and field not in b:
            continue
        if field not in a or field not in b:
            raise ValueError('Paired initial measurement coverage mismatch: '+field)
        values=list(zip(flat(a[field]),flat(b[field]),strict=True))
        tolerance=1e-10 if field=='inertia_readback' else 1e-6
        if not values or any(not math.isfinite(x) or not math.isfinite(y) or abs(x-y)>tolerance for x,y in values):
            raise ValueError('Paired initial physical state mismatch: '+field)


def audit_bindings(out, reg, frozen):
    from physicalevobench.core.learning import compact, event_feedback
    checks = 0
    for i, group in enumerate(reg['conditions']):
        if {c['seed'] for c in group['support']} & {c['seed'] for c in group['query']}:
            raise ValueError('Support/query seed overlap')
        directory = out/f'instance-{i}'
        initials = {}
        for name in ('frozen', 'designer', 'search', 'feedback', 'deletion'):
            if name in ('designer', 'feedback'):
                calls = sorted((directory/name/'model_calls').glob('call-*'))
                usages = [read(c/'usage.json') for c in calls if (c/'usage.json').exists()]
                if len(usages) != len(calls):
                    if not (directory/name/'validity_failure.json').exists():
                        raise ValueError('Actual model usage missing')
                else:
                    actual = {'calls': len(usages), 'input_tokens': sum(u['input_tokens'] for u in usages),
                              'output_tokens': sum(u['output_tokens'] for u in usages)}
                    if read(directory/name/'model_calls/budget.json') != actual:
                        raise ValueError('Model usage mismatch')
                    for key, cap in reg['model_limits_per_method'].items():
                        if actual[key] > cap and not (directory/name/'validity_failure.json').exists():
                            raise ValueError('Invalid cumulative model budget')
                if name == 'designer' and (directory/name/'native').exists():
                    raise ValueError('No-feedback designer accessed physics')
                if (directory/name/'validity_failure.json').exists():
                    if frozen['artifacts'][i][name] != 'INVALID_PARTICIPANT_SUBMISSION':
                        raise ValueError('Invalid participant omitted or misrepresented')
                    continue
                receipt = read(directory/name/'freeze_receipt.json')
                if receipt['at'] > frozen['at']:
                    raise ValueError('Artifact frozen after test boundary')
                response = read(directory/name/f"proposal-{receipt['proposal_index']:02d}.json")
                selected = Program.from_dict(json.loads(response['program_json']))
                path = directory/name/'artifact.json'
                art = load(path)
                if (response['tool'] != 'freeze' or art['payload']['skill'] != selected.to_dict() or
                        art['payload']['memory'] != response['memory'] or
                        receipt['program_hash'] != selected.sha256):
                    raise ValueError('Retained artifact was not selected by actual model')
                history = read(directory/name/'history.json') if (directory/name/'history.json').exists() else []
                for j, call in enumerate(calls):
                    request = read(call/'request.json')
                    if request['history'] != compact(history[:j]):
                        raise ValueError('Participant history differs from actual prior trials')
                    if reg.get('participant_context_version')=='public-context-v3':
                        prior=[h['memory'] for h in history[:j] if 'memory' in h]
                        if request.get('current_memory')!=(prior[-1] if prior else ''):
                            raise ValueError('Participant memory did not survive the serialized boundary')
                        for k,h in enumerate(history[:j]):
                            if h['tool']!='validation_error':
                                chosen=read(directory/name/f'proposal-{k:02d}.json')
                                if (h['memory']!=chosen['memory'] or
                                        (h['tool']=='run_trial' and h['practice_handle']!=chosen['practice_handle'])):
                                    raise ValueError('Past experiment identity or learner notes were lost')
                trials = [j for j, item in enumerate(history) if item['tool'] == 'run_trial']
                if art['payload']['budget_used'] != len(trials):
                    raise ValueError('Artifact learning cost differs from actual trials')
                if name == 'feedback':
                    native = directory/name/'native'
                    jobs = sorted((native/'requests').glob('*.json'))
                    if len(jobs) != len(trials):
                        raise ValueError('Unauthorized or missing learning trial')
                    for jobfile, j in zip(jobs, trials, strict=True):
                        job = read(jobfile)
                        response_trial = read(directory/name/f'proposal-{j:02d}.json')
                        chosen = int(response_trial['practice_handle'].removeprefix('practice-'))
                        condition = group['support'][chosen]
                        if (job['condition'] != {k: v for k, v in condition.items() if k != 'public_goal'} or
                                job['public_goal'] != condition['public_goal'] or
                                job['program'] != json.loads(response_trial['program_json']) or
                                job['identity']['candidate_index'] != j):
                            raise ValueError('Physical trial differs from participant choice')
                        row = read(native/'episodes'/job['episode_id']/'episode.json')
                        if history[j]['feedback'] != event_feedback(native, row):
                            raise ValueError('Learner received invented physical feedback')
            elif name=='search':
                path=directory/'search/artifact.json'
                art=load(path)
                search=read(directory/'search/candidate_registration.json')
                selection=read(directory/'search/selection.json')
                rows=[read(directory/'search/native'/f'responses/{j:03d}.json') for j in range(8)]
                scores=[sum(rows[2*j+k]['success'] for k in range(2)) for j in range(4)]
                chosen=max(range(4),key=lambda j:scores[j])
                if (selection['batch_scores']!=scores or selection['selected']!=chosen or
                        art['payload']['skill']!=search['programs'][chosen]):
                    raise ValueError('Search selection differs from common batch outcomes')
                for j,row in enumerate(rows):
                    job=read(directory/'search/native'/f'requests/{j:03d}.json')
                    c=group['support'][j%2]
                    if (job['condition']!={k:v for k,v in c.items() if k!='public_goal'} or
                            job['public_goal']!=c['public_goal'] or job['program']!=search['programs'][j//2]):
                        raise ValueError('Search candidates compared on different conditions')
            else:
                path = directory/f'{name}.json'
                art = load(path)
            if (art['effective_artifact_hash'] != frozen['artifacts'][i][name] or
                    art['payload']['executor'] != 'contact-integral-v1/'+reg['source_commit']):
                raise ValueError('Frozen artifact or executor changed')
            native = directory/f'test-{name}'
            if read(native/'source_identity.json')['commit'] != reg['source_commit']:
                raise ValueError('Physical executor source changed')
            requests = sorted((native/'requests').glob('*.json'))
            if len(requests) != len(group['query']):
                raise ValueError('Missing assigned query condition')
            for jobfile, c in zip(requests, group['query'], strict=True):
                job = read(jobfile)
                if (job['condition'] != {k: v for k, v in c.items() if k != 'public_goal'} or
                        job['public_goal'] != c['public_goal'] or job['program'] != art['payload']['skill'] or
                        job['reference_config'] != reg['reference']['reference_config'] or
                        job['identity']['effective_artifact_hash'] != art['effective_artifact_hash']):
                    raise ValueError('Test program/condition differs from frozen assignment')
                initial = initial_for_pair(native/'episodes'/job['episode_id'])
                key = c['condition_id']
                if key in initials:
                    assert_initial_pair(initials[key], initial)
                else:
                    initials[key] = initial
                checks += 1
        if load(directory/'frozen.json')['payload']['skill'] != load(directory/'deletion.json')['payload']['skill']:
            raise ValueError('Deletion must restore exact common initial executable')
    return {'status': 'PASS', 'paired_test_bindings': checks,
            'scope': 'Model choices, no-feedback isolation, freeze, assignment, budgets, reset pairing'}


def verify_sources(directory):
    identity = read(directory/'source_identity.json')
    source = Path(read(directory/'launch.json')['runtime_source'])
    if source.exists():
        for name, expected in identity['files'].items():
            if sha256(source/name) != expected:
                raise ValueError('Frozen runtime source changed')
    return digest(identity)
