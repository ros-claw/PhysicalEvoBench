"""Fixed reference + identical-reference replay on the actual query manifests."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.execution_identity import validate_execution
from physicalevobench.core.learning_audit import assert_initial_pair, initial_for_pair
from physicalevobench.core.program import Program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.development.place import make_job
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now


def read(path):
    return json.loads(Path(path).read_text())


def run(root, out, extension, prospective, qualification, gpu):
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit replay calibration before registration')
    q = read(qualification)
    base = read(extension/'registration.json')['reference']
    validate_execution(root, q, base)
    program = Program.from_dict(read(root/'configs/learning/reference_aperture.json'))
    if program.sha256 != q['reference_hash']:
        raise ValueError('Cannot change the qualified reference')
    source = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    cases = []
    for directory in (extension, prospective):
        reg = read(directory/'registration.json')
        groups = reg['conditions']
        if reg['schema'] == 'esl-learning-1':
            groups = [g['query'] for g in groups]
        for i, group in enumerate(groups):
            for j, c in enumerate(group):
                cases.append({'condition': c, 'source_study': directory.name,
                              'source_registration_sha256': sha256(directory/'registration.json'),
                              'source_instance': i, 'source_episode': f'query-{j:03d}'})
    cfg = {**read(extension/'registration.json')['cfg'], 'physical_budget': len(cases)*2}
    jobs = []
    for i, case in enumerate(cases):
        names = ['strong', 'identity_strong'] if i % 2 == 0 else ['identity_strong', 'strong']
        for name in names:
            job = make_job(program, case['condition'], f'reference-{len(jobs):03d}', name)
            job['reference_config'] = base['reference_config']
            job['identity']['case_index'] = i
            jobs.append(job)
    out.mkdir(parents=True, exist_ok=False)
    save_json(out/'registration.json', {'schema': 'esl-reference-replay-1', 'mode': 'QUALIFICATION_REPLAY',
              'at': now(), 'source_commit': source, 'physical_budget': len(jobs), 'cfg': cfg,
              'cases': cases, 'jobs': jobs, 'reference_program_hash': program.sha256,
              'qualification': q, 'new_learning_instances': 0, 'model_calls': 0,
              'scope': 'Fixed reference reliability, same-program noise and paired source initial states; not learning or reference tuning'})
    save_json(out/'status.json', {'status': 'RUNNING', 'at': now()})
    session = NativeSession(root, out/'native', source, cfg, gpu)
    try:
        session.ready()
        for job in jobs:
            session.trial(job)
    finally:
        session.close()
    result = summarize(out)
    save_json(out/'status.json', {'status': 'COMPLETED', 'at': now(), 'episodes': result['episodes']})
    print(json.dumps(result, indent=2))


def summarize(out):
    reg = read(out/'registration.json')
    rows = audit_session(out/'native')
    if len(rows) != reg['physical_budget']:
        raise ValueError('Reference replay assignment incomplete')
    groups = {}
    initials = {}
    for i, row in enumerate(rows):
        job = read(out/'native/requests'/f'{i:03d}.json')
        if job != reg['jobs'][i] or Program.from_dict(job['program']).sha256 != reg['reference_program_hash']:
            raise ValueError('Fixed reference/assignment changed')
        case_index = job['identity']['case_index']
        case = reg['cases'][case_index]
        key = case['source_study']+'/'+str(case['source_instance'])
        groups.setdefault(key, {}).setdefault(job['identity']['method'], []).append(row['success'])
        initial = initial_for_pair(out/'native/episodes'/row['episode_id'])
        if case_index in initials:
            assert_initial_pair(initials[case_index], initial)
        else:
            initials[case_index] = initial
    result = {'schema': 'fixed-reference-replay-results-1', 'audit': 'PASS', 'episodes': len(rows),
              'groups': groups, 'new_learning_instances': 0, 'model_calls': 0,
              'scope': 'Reference and identical reference only; same-condition source pairing audited after all source queries complete'}
    save_json(out/'results.json', result)
    return result


def audit_source_pairing(out, source_roots):
    reg = read(out/'registration.json')
    rows = [json.loads(s) for s in (out/'native/episodes.jsonl').read_text().splitlines()]
    checked = 0
    for i, row in enumerate(rows):
        case = reg['cases'][reg['jobs'][i]['identity']['case_index']]
        source = source_roots[case['source_study']]
        if sha256(source/'registration.json') != case['source_registration_sha256']:
            raise ValueError('Paired source registration changed')
        original = source/f"instance-{case['source_instance']}"/'test-frozen'/'episodes'/case['source_episode']
        initial = initial_for_pair(out/'native/episodes'/row['episode_id'])
        assert_initial_pair(initial, initial_for_pair(original))
        checked += 1
    return {'status': 'PASS', 'source_query_initial_pairs': checked}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--extension', required=True)
    p.add_argument('--prospective', required=True)
    p.add_argument('--qualification', default='configs/learning/qualification.json')
    p.add_argument('--gpu', type=int, default=2)
    a = p.parse_args()
    run(Path.cwd(), Path(a.output).absolute(), Path(a.extension), Path(a.prospective), Path(a.qualification), a.gpu)


if __name__ == '__main__':
    main()
