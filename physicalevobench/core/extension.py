"""Prospective new-combination queries of already-frozen artifacts; zero new learning."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.artifact import load
from physicalevobench.core.audit import audit_session
from physicalevobench.core.execution_identity import validate_execution
from physicalevobench.core.learning_audit import assert_initial_pair
from physicalevobench.core.metrics import compare
from physicalevobench.core.problem import PROFILE, fresh, validate_problem
from physicalevobench.core.program import Program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.development.place import make_job
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.stability.metrics import paired_interval

ARMS = ('frozen', 'designer', 'search', 'feedback', 'deletion')


def read(path):
    return json.loads(Path(path).read_text())


def run(root, out, origin, qualification, gpu):
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit extension protocol and source before launch')
    reg = read(origin/'registration.json')
    boundary = read(origin/'all_frozen.json')
    receipt = read(qualification)
    validate_problem(PROFILE, receipt)
    validate_execution(root, receipt, reg['reference'])
    if receipt['execution_files'] != reg['qualification']['execution_files']:
        raise ValueError('Extension must retain exact original execution semantics')
    source = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    cs = fresh(root, out.parent, 2026103012, reg['instances']*4, PROFILE['query_goal_positions'], 'factorial-query')
    groups = [cs[i*4:i*4+4] for i in range(reg['instances'])]
    out.mkdir(parents=True, exist_ok=False)
    artifacts = []
    for i in range(reg['instances']):
        group = {}
        for name in ARMS:
            path = origin/f'instance-{i}'/(f'{name}.json' if name in ('frozen', 'deletion') else f'{name}/artifact.json')
            art = load(path)
            if art['effective_artifact_hash'] != boundary['artifacts'][i][name]:
                raise ValueError('Original frozen artifact changed')
            save_json(out/'artifacts'/f'instance-{i}-{name}.json', art)
            group[name] = art
        artifacts.append(group)
    registration = {'schema': 'esl-frozen-extension-1', 'mode': 'EXPLORATORY_BENCHMARK',
                    'at': now(), 'source_commit': source, 'original_executor_source': reg['source_commit'],
                    'origin_registration_sha256': sha256(origin/'registration.json'),'origin_registration':reg,
                    'origin_global_freeze': boundary, 'conditions': groups, 'instances': reg['instances'],
                    'physical_budget': 20*reg['instances'], 'profile': PROFILE, 'qualification': receipt,
                    'cfg': reg['cfg'], 'reference': reg['reference'], 'gpu': gpu,
                    'new_model_calls': 0, 'new_training_episodes': 0,
                    'scope': 'Query distribution developed after original Frozen ceiling; all old outcomes retained, artifacts frozen before redesign, not new learning instances or confirmatory superiority'}
    save_json(out/'registration.json', registration)
    save_json(out/'all_frozen.json', {'at': now(), 'artifacts': [
        {n: a['effective_artifact_hash'] for n, a in group.items()} for group in artifacts]})
    save_json(out/'status.json', {'status': 'RUNNING', 'at': now()})
    for i, group in enumerate(artifacts):
        names = ARMS if i % 2 == 0 else tuple(reversed(ARMS))
        for name in names:
            art = load(out/'artifacts'/f'instance-{i}-{name}.json')
            cfg = {**reg['cfg'], 'physical_budget': 4}
            session = NativeSession(root, out/f'instance-{i}'/f'test-{name}', source, cfg, gpu)
            try:
                session.ready()
                for j, c in enumerate(groups[i]):
                    job = make_job(Program.from_dict(art['payload']['skill']), c, f'query-{j:03d}', name)
                    job['reference_config'] = reg['reference']['reference_config']
                    job['identity'].update(effective_artifact_hash=art['effective_artifact_hash'],
                                           learning_run_id=art['payload']['learning_run_id'])
                    session.trial(job)
            finally:
                session.close()
    result = summarize(out)
    save_json(out/'status.json', {'status': 'COMPLETED', 'at': now(), 'episodes': result['physical_episodes']})
    print(json.dumps(result, indent=2))


def summarize(out):
    reg = read(out/'registration.json')
    frozen = read(out/'all_frozen.json')
    validate_problem(reg['profile'], reg['qualification'])
    if reg['origin_global_freeze']['at']>=reg['at']:
        raise ValueError('Original artifacts were not frozen before new query registration')
    old_seeds={c['seed'] for group in reg['origin_registration']['conditions'] for values in group.values() for c in values}
    if old_seeds & {c['seed'] for group in reg['conditions'] for c in group}:
        raise ValueError('New query reused original support/query seeds')
    results = []
    total = controls = samples = 0
    for i, conditions in enumerate(reg['conditions']):
        initials = {}
        scores = {}
        for name in ARMS:
            art = load(out/'artifacts'/f'instance-{i}-{name}.json')
            if (art['effective_artifact_hash'] != frozen['artifacts'][i][name] or
                    art['effective_artifact_hash'] != reg['origin_global_freeze']['artifacts'][i][name]):
                raise ValueError('Imported frozen artifact identity changed')
            worker = out/f'instance-{i}'/f'test-{name}'
            if read(worker/'launch.json')['started_at'] <= frozen['at']:
                raise ValueError('Extension query before artifact freeze')
            rows = audit_session(worker)
            if len(rows) != len(conditions):
                raise ValueError('Missing paired query')
            for j, (r, c) in enumerate(zip(rows, conditions, strict=True)):
                job = read(worker/'requests'/f'{j:03d}.json')
                if (job['program'] != art['payload']['skill'] or job['public_goal'] != c['public_goal'] or
                        job['condition'] != {k: v for k, v in c.items() if k != 'public_goal'} or
                        job['reference_config'] != reg['reference']['reference_config'] or
                        r['core_identity']['effective_artifact_hash'] != art['effective_artifact_hash']):
                    raise ValueError('Frozen query assignment mismatch')
                initial = read(worker/'episodes'/r['episode_id']/'initial_capture.json')
                if c['condition_id'] in initials:
                    assert_initial_pair(initials[c['condition_id']], initial)
                else:
                    initials[c['condition_id']] = initial
            scores[name] = {r['condition_id']: r['success'] for r in rows}
            total += len(rows)
            controls += sum(r['steps'] for r in rows)
            samples += sum(r['diagnostic']['physics_samples'] for r in rows)
        results.append({'learning_instance': i, 'scores': scores,
                        'feedback_gain': compare(scores['designer'], scores['feedback']),
                        'artifact_gain': compare(scores['deletion'], scores['feedback']),
                        'search_gain': compare(scores['frozen'], scores['search'])})
    if total > reg['physical_budget']:
        raise ValueError('Extension budget exceeded')
    intervals = {name: paired_interval([[int(g['scores']['feedback'][k])-int(g['scores'][baseline][k])
                                        for k in g['scores']['feedback']] for g in results])
                 for name, baseline in [('feedback_gain', 'designer'), ('artifact_gain', 'deletion')]}
    result = {'schema': 'esl-frozen-extension-results-1', 'audit': 'PASS', 'instances': results,
              'paired_conditional_intervals': intervals, 'physical_episodes': total,
              'controls': controls, 'physics_samples': samples, 'new_learning_instances': 0,
              'new_model_calls': 0, 'new_training_episodes': 0,
              'scope': 'Exploratory factorial-query extension of same two frozen learning instances; original query ceiling reported separately, not confirmatory stability'}
    save_json(out/'results.json', result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--origin', required=True)
    p.add_argument('--qualification', required=True)
    p.add_argument('--gpu', type=int, default=0)
    a = p.parse_args()
    run(Path.cwd(), Path(a.output).absolute(), Path(a.origin), Path(a.qualification), a.gpu)


if __name__ == '__main__':
    main()
