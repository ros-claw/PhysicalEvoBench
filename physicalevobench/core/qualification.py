"""Task qualification is separate from method learning and from old T1 gates."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.pilot import worker_config
from physicalevobench.core.program import Program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.development.place import candidate, conditions, make_job
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import digest, load


def run(root, out, reference, program_file, gpu):
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Freeze qualification source before launch')
    source = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    base = load(reference)
    strong = Program.from_dict(json.loads(program_file.read_text()))
    cs = conditions('qualification1030', 2026103003, 4)
    for i, c in enumerate(cs):
        c['public_goal'] = [.62, .12, .021] if i < 2 else [.60, -.12, .021]
    jobs = []
    programs = {'starter': candidate('starter'), 'aperture_guard': candidate('aperture'),
                'strong': strong, 'identity_strong': strong}
    for i, c in enumerate(cs):
        names = list(programs)
        names = names[i:]+names[:i]
        for name in names:
            job = make_job(programs[name], c, f'qualification-{len(jobs):03d}', name)
            job['reference_config'] = base['reference_config']
            jobs.append(job)
    for c in cs[:2]:
        job = make_job(strong, c, f'qualification-{len(jobs):03d}', 'force_open')
        job.update(reference_config=base['reference_config'], force_open=True)
        jobs.append(job)
    cfg = worker_config(base, len(jobs))
    cfg.update(core_task='place', task_version='core-place-public-v3-dev', horizon_s=20.,
               control_profile='contact-integral-v1', public_goal=cs[0]['public_goal'])
    out.mkdir(parents=True, exist_ok=False)
    save_json(out/'registration.json', {'schema': 'esl-qualification-1', 'mode': 'QUALIFICATION',
              'registered_at': now(), 'source_commit': source, 'physical_budget': len(jobs),
              'jobs': jobs, 'cfg': cfg, 'programs': {n: p.to_dict() for n, p in programs.items()},
              'criteria': 'strong 4/4, forced-open 0/2; strong-starter difference exceeds identity difference; no hard events',
              'scope': 'Finite task qualification, not evidence that a learner improves'})
    session = NativeSession(root, out/'native', source, cfg, gpu)
    try:
        session.ready()
        for job in jobs:
            session.trial(job)
    finally:
        session.close()
    rows = audit_session(out/'native')
    scores = {name: [r['success'] for r in rows if r['core_identity']['method'] == name]
              for name in [*programs, 'force_open']}
    gap = sum(scores['strong'])-sum(scores['starter'])
    noise = abs(sum(scores['strong'])-sum(scores['identity_strong']))
    qualified = (all(scores['strong']) and not any(scores['force_open']) and gap > noise and
                 not any(r['diagnostic']['hard_boundary_terminated'] for r in rows))
    receipt = {'schema': 'esl-task-qualification-1', 'status': 'QUALIFIED' if qualified else 'DEV',
               'at': now(), 'source_commit': source, 'registration_sha256': digest(json.loads((out/'registration.json').read_text())),
               'task_version': cfg['task_version'], 'control_profile': cfg['control_profile'],
               'reference_hash': strong.sha256, 'starter_hash': programs['starter'].sha256,
               'scores': scores, 'strategy_gap_count': gap, 'identity_gap_count': noise,
               'scope': 'Small finite qualification; not a population significance or learning-effect claim'}
    save_json(out/'qualification.json', receipt)
    print(json.dumps(receipt, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--reference', default='configs/core/frozen_reference.json')
    p.add_argument('--program', required=True)
    p.add_argument('--gpu', type=int, default=2)
    a = p.parse_args()
    run(Path.cwd(), Path(a.output).absolute(), Path(a.reference), Path(a.program), a.gpu)


if __name__ == '__main__':
    main()
