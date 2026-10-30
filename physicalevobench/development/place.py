"""Independent hypothesis-driven release development, with prelaunch cost reservations."""

import argparse
import json
import random
from pathlib import Path

from physicalevobench.core.audit import audit_session
from physicalevobench.core.expressions import comparison as cmp
from physicalevobench.core.expressions import relative
from physicalevobench.core.pilot import worker_config
from physicalevobench.core.program import Program, initial_program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.v02.reference_artifact import load


def starter_program():
    value = initial_program(True).to_dict()
    value['schema'] = 'core-skill-graph-2'
    for n in value['nodes']:
        if n['target'] in ('place_above', 'place_lower', 'place_retreat'):
            n['target'] = relative('goal', n['offset_m'])
    return Program.from_dict(value)


def candidate(kind):
    value = starter_program().to_dict()
    for n in value['nodes']:
        if n['id'] == 'lower' and kind in ('settle', 'settle_open'):
            n['guard'] = {'all': [cmp('goal_xy_error', 'le', .02),
                                  cmp('goal_z_error', 'le', .025), cmp('object_speed', 'le', .07)]}
            n['dwell_s'] = .12
        if n['id'] == 'release' and kind in ('open', 'settle_open'):
            n['guard'] = {'all': [cmp('finger_min', 'ge', .038),
                                  cmp('finger_contact_max', 'le', .5)]}
            n['dwell_s'] = .10
    return Program.from_dict(value)


def conditions(label, seed, count):
    rng = random.Random(seed)
    return [{'condition_id': f'{label}-{i:02d}', 'seed': rng.randrange(2**31),
             'object_mass_kg': .1 if i % 2 == 0 else .4, 'split': label,
             'public_goal': [.62, .12, .021]} for i in range(count)]


def make_job(program, c, episode, name):
    # Goal is public; evaluator-only fields never enter the participant context.
    condition = {k: v for k, v in c.items() if k != 'public_goal'}
    return {'episode_id': episode, 'condition': condition, 'program': program.to_dict(),
            'public_goal': c['public_goal'], 'identity': {'method': name, 'program_hash': program.sha256}}


def run(root, out, reference, gpu, variants, count, profile):
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Commit development source before launch')
    if any(v not in ('starter', 'open', 'settle', 'settle_open') for v in variants):
        raise ValueError('Unknown declared diagnostic intervention')
    base = load(reference)
    source = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    jobs = []
    cs = conditions('dev1030', 2026103002, count)
    for i, c in enumerate(cs):
        for v in variants:
            job = make_job(candidate(v), c, f'dev-{len(jobs):03d}', v)
            job['reference_config'] = base['reference_config']
            jobs.append(job)
    spent = 0
    for path in out.parent.glob('peb-esl-dev-*/registration.json'):
        previous = json.loads(path.read_text())
        spent += previous['physical_budget']
    if spent+len(jobs) > 48:
        raise ValueError('Declared 48-episode DEV resource ceiling exceeded')
    cfg = worker_config(base, len(jobs))
    cfg.update(core_task='place', task_version='core-place-public-v3-dev', horizon_s=20.,
               control_profile=profile, public_goal=cs[0]['public_goal'])
    out.mkdir(parents=True, exist_ok=False)
    save_json(out/'registration.json', {'schema': 'esl-development-1', 'mode': 'DEV',
              'source_commit': source, 'registered_at': now(), 'physical_budget': len(jobs),
              'development_ceiling': 48, 'prior_reserved': spent, 'jobs': jobs, 'cfg': cfg,
              'hypotheses': {'open': 'Wait for actual aperture/contact loss before retreat',
                             'settle': 'Wait for low object speed near supported goal before opening'},
              'scope': 'Engineering interventions; no learning or heldout claims'})
    save_json(out/'status.json', {'status': 'RUNNING'})
    session = NativeSession(root, out/'native', source, cfg, gpu)
    try:
        session.ready()
        for job in jobs:
            session.trial(job)
    finally:
        session.close()
    rows = audit_session(out/'native')
    result = {'mode': 'DEV', 'audit': 'PASS', 'episodes': len(rows), 'methods': {}}
    for v in variants:
        selected = [r for r in rows if r['core_identity']['method'] == v]
        result['methods'][v] = {'successes': sum(r['success'] for r in selected),
                                 'episodes': len(selected), 'details': [r['place'] for r in selected]}
    save_json(out/'result.json', result)
    save_json(out/'status.json', {'status': 'COMPLETED', 'episodes': len(rows)})
    print(json.dumps(result, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--gpu', type=int, default=2)
    p.add_argument('--reference', default='configs/core/frozen_reference.json')
    p.add_argument('--variants', default='starter,open,settle,settle_open')
    p.add_argument('--conditions', type=int, default=2, choices=range(1, 5))
    p.add_argument('--control-profile', default='contact-integral-v1',
                   choices=['contact-integral-v1', 'phase-integral-legacy'])
    a = p.parse_args()
    run(Path.cwd(), Path(a.output).absolute(), Path(a.reference), a.gpu,
        a.variants.split(','), a.conditions, a.control_profile)


if __name__ == '__main__':
    main()
