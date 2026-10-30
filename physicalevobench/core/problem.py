"""Learning-problem qualification includes the query distribution, not only reachability."""

import argparse
import json
import random
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.execution_identity import EXECUTION_FILES
from physicalevobench.core.pilot import worker_config
from physicalevobench.core.program import Program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.development.place import make_job, starter_program
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.v02.reference_artifact import digest, load

PROFILE = {'learning_problem_id': 'place-release-factorial-v2',
           'support_goal_positions': [[.62, .12, .021], [.60, -.12, .021]],
           'query_goal_positions': [[.60, .12, .021], [.62, -.12, .021]],
           'editable_space': 'core-skill-graph-2', 'execution_profile': 'contact-integral-v1',
           'task_version': 'core-place-public-v3-dev', 'scoring': 'core-place-score-1',
           'knowledge_link': 'Same release mechanics; X and Y goal factors recombine at query. Hidden mass classes repeat, reset seeds are disjoint.'}


def validate_problem(profile, receipt):
    if (receipt.get('status') != 'QUALIFIED' or receipt.get('learning_problem_sha256') != digest(profile)):
        raise ValueError('Learning Problem query distribution is not qualified')


def fresh(root, parent, stream, count, goals, label):
    excluded = published_seeds(root)
    for p in parent.glob('peb-*/registration.json'):
        excluded.update(registered_seed_values(json.loads(p.read_text())))
    rng = random.Random(stream)
    result = []
    for i in range(count):
        seed = rng.randrange(2**31)
        while seed in excluded:
            seed = rng.randrange(2**31)
        excluded.add(seed)
        result.append({'condition_id': f'{label}-{i}', 'split': label, 'seed': seed,
                       'object_mass_kg': .1 if i % 2 == 0 else .4,
                       'public_goal': goals[(i//2) % len(goals)]})
    return result


def run(root, out, reference, program_file, gpu):
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Freeze Learning Problem qualification source before launch')
    source = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    base = load(reference)
    strong = Program.from_dict(json.loads(program_file.read_text()))
    cs = fresh(root, out.parent, 2026103011, 4, PROFILE['query_goal_positions'], 'factorial-qualification')
    programs = {'starter': starter_program(), 'strong': strong, 'identity_strong': strong}
    jobs = []
    for i, c in enumerate(cs):
        names = list(programs)
        names = names[i % 3:]+names[:i % 3]
        for name in names:
            job = make_job(programs[name], c, f'problem-{len(jobs):03d}', name)
            job['reference_config'] = base['reference_config']
            jobs.append(job)
    for c in cs[:2]:
        job = make_job(strong, c, f'problem-{len(jobs):03d}', 'force_open')
        job.update(reference_config=base['reference_config'], force_open=True)
        jobs.append(job)
    cfg = worker_config(base, len(jobs))
    cfg.update(core_task='place', task_version=PROFILE['task_version'], horizon_s=20.,
               control_profile=PROFILE['execution_profile'], public_goal=cs[0]['public_goal'])
    out.mkdir(parents=True, exist_ok=False)
    save_json(out/'registration.json', {'schema': 'esl-problem-qualification-1', 'mode': 'QUALIFICATION',
              'source_commit': source, 'at': now(), 'physical_budget': len(jobs), 'jobs': jobs,
              'profile': PROFILE, 'baseline_reference':base,'cfg': cfg, 'programs': {n: p.to_dict() for n, p in programs.items()},
              'criteria': 'strong4/4, negative0/2, strategy count gap greater than identity count gap, zero hard boundary',
              'selection': 'Factor recombination defined after original Frozen ceiling, before these outcomes; no Agent winning criterion'})
    session = NativeSession(root, out/'native', source, cfg, gpu)
    try:
        session.ready()
        for job in jobs:
            session.trial(job)
    finally:
        session.close()
    rows = audit_session(out/'native')
    scores = {n: [r['success'] for r in rows if r['core_identity']['method'] == n]
              for n in [*programs, 'force_open']}
    gap = sum(scores['strong'])-sum(scores['starter'])
    noise = abs(sum(scores['strong'])-sum(scores['identity_strong']))
    qualified = (all(scores['strong']) and not any(scores['force_open']) and gap > noise and
                 not any(r['diagnostic']['hard_boundary_terminated'] for r in rows))
    identity = json.loads((out/'native/source_identity.json').read_text())
    receipt = {'schema': 'learning-problem-qualification-1', 'status': 'QUALIFIED' if qualified else 'DEV',
               'source_commit': source, 'at': now(), 'registration_sha256': digest(json.loads((out/'registration.json').read_text())),
               'learning_problem': PROFILE, 'learning_problem_sha256': digest(PROFILE),
               'scores': scores, 'strategy_gap_count': gap, 'identity_gap_count': noise,
               'execution_files': {p: identity['files'][p] for p in EXECUTION_FILES},
               'initial_reference_sha256': digest(base), 'reference_hash': strong.sha256,
               'starter_hash': starter_program().sha256, 'task_version': cfg['task_version'],
               'control_profile': cfg['control_profile'],
               'scope': 'Finite query-family qualification; no selected Agent performance criterion'}
    save_json(out/'qualification.json', receipt)
    save_json(out/'status.json', {'status': 'COMPLETED', 'at': now(), 'episodes': len(rows)})
    print(json.dumps(receipt, indent=2))



def audit_receipt(out):
    reg=json.loads((out/'registration.json').read_text())
    q=json.loads((out/'qualification.json').read_text())
    data=audit_session(out/'native')
    scores={name:[r['success'] for r in data if r['core_identity']['method']==name]
            for name in ('starter','strong','identity_strong','force_open')}
    gap=sum(scores['strong'])-sum(scores['starter'])
    noise=abs(sum(scores['strong'])-sum(scores['identity_strong']))
    qualified=(all(scores['strong']) and not any(scores['force_open']) and gap>noise and
               not any(r['diagnostic']['hard_boundary_terminated'] for r in data))
    if (q['scores']!=scores or q['strategy_gap_count']!=gap or q['identity_gap_count']!=noise or
            q['status']!=('QUALIFIED' if qualified else 'DEV') or
            q['learning_problem_sha256']!=digest(reg['profile']) or
            q['registration_sha256']!=digest(reg) or
            q['initial_reference_sha256']!=digest(reg['baseline_reference'])):
        raise ValueError('Problem qualification differs from original registration/raw physical response')
    identity=json.loads((out/'native/source_identity.json').read_text())
    if q['execution_files']!={p:identity['files'][p] for p in EXECUTION_FILES}:
        raise ValueError('Qualified execution identity differs from actual native source')
    for i,job in enumerate(reg['jobs']):
        if json.loads((out/'native/requests'/f'{i:03d}.json').read_text())!=job:
            raise ValueError('Qualification execution differs from planned intervention')
    return {'status':'PASS','episodes':len(data),'qualification_status':q['status'],'scores':scores}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--reference', default='configs/core/frozen_reference.json')
    p.add_argument('--program', default='configs/learning/reference_aperture.json')
    p.add_argument('--gpu', type=int, default=0)
    a = p.parse_args()
    run(Path.cwd(), Path(a.output).absolute(), Path(a.reference), Path(a.program), a.gpu)


if __name__ == '__main__':
    main()
