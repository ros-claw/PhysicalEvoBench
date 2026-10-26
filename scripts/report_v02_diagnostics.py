"""Audited development summaries; never pools these with historical efficacy."""

import argparse
import csv
import itertools
import json
import math
import random
from collections import defaultdict
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read
from physicalevobench.v02.audit import audit_run, records


def quantile(values, p):
    values = sorted(values)
    return values[math.ceil(p*len(values))-1] if values else 0.


def risk(row, meta):
    depths = row['diagnostic']['maximum_joint_depths']
    return any(d > (.01 if 'finger' in n else .1)
               for n,d in zip(meta['joint_names'], depths, strict=True))


def summarize(entries):
    return {'episodes': len(entries), 'instant': sum(e['instant'] for e in entries),
            'holding': sum(e['holding'] for e in entries),
            'hard_events': sum(e['hard_event'] for e in entries),
            'any_violation': sum(e['any_violation'] for e in entries),
            'maximum_finger_depth_m': max(e['finger_depth_m'] for e in entries),
            'median_episode_max_finger_depth_m': quantile([e['finger_depth_m'] for e in entries], .5),
            'q95_episode_max_finger_depth_m': quantile([e['finger_depth_m'] for e in entries], .95),
            'maximum_holding_span_s': max(e['holding_span_s'] for e in entries)}


def first_difference(left, right, fields):
    for i, (a,b) in enumerate(zip(left,right)):
        changed = [f for f in fields if a[f] != b[f]]
        if changed:
            return {'sample': i, 'fields': changed}
    if len(left) != len(right):
        return {'sample': min(len(left),len(right)), 'fields': ['episode_length']}
    return None


def report(directory):
    directory = Path(directory)
    audit = audit_run(directory)
    reg = read(directory/'registration.json')
    entries = []
    for row in read(directory/'results.json')['episodes']:
        worker = directory/row['worker']
        meta = read(worker/'control_semantics.json')
        episode = worker/'episodes'/row['episode_id']
        state = read(episode/'initial_state.json')
        metric = row['diagnostic']
        finger_depth = max(d for n,d in zip(meta['joint_names'],metric['maximum_joint_depths'],strict=True) if 'finger' in n)
        entries.append({'worker': row['worker'], 'episode_id': row['episode_id'],
                        'condition_id': row['condition_id'], 'mass_kg': state['condition']['object_mass_kg'],
                        'instant': metric['holding']['instant_success'],
                        'holding': metric['holding']['stable_success'],
                        'hard_event': risk(row,meta), 'any_violation': metric['first_violation'] is not None,
                        'finger_depth_m': finger_depth,
                        'holding_span_s': metric['holding']['maximum_holding_span_s']})
    result = {'schema': 'v02-development-report-1', 'audit': audit,
              'registration_sha256': sha256(directory/'registration.json'),
              'learning_updates': 0, 'episodes': entries,
              'scope': 'fixed-policy development diagnosis, no stable self-evolution claim'}
    if reg['phase'] == 'representatives':
        paired = defaultdict(dict)
        for entry in entries:
            prefix, layer = entry['worker'].rsplit('-',1)
            paired[prefix][layer] = entry
        details = []
        for prefix, arms in sorted(paired.items()):
            a,b = arms['NumericalOnly'],arms['TargetBounded']
            dirs = [directory/e['worker']/'episodes'/e['episode_id'] for e in (a,b)]
            violations = []
            for entry, ep in zip((a,b), dirs, strict=True):
                row = read(ep/'episode.json')
                first = row['diagnostic']['first_violation']
                evidence = None
                if first:
                    frame = next(f for f in records(ep/'physics.jsonl.gz')
                                 if f['physics_step_global'] == first['physics_step_global'])
                    evidence = {'first': first, 'joint_velocity': frame['joint_velocity'],
                                'contacts': frame['contacts'], 'applied_torque': frame['applied_torque'],
                                'warning': 'coincident telemetry does not identify a unique cause'}
                violations.append(evidence)
            details.append({'sample': prefix, 'arms': arms,
                            'initial_state_exact_match': read(dirs[0]/'initial_state.json') == read(dirs[1]/'initial_state.json'),
                            'first_violation_evidence': violations})
        result['paired_cases'] = details
        result['by_layer'] = {layer: summarize([e for e in entries if e['worker'].endswith(layer)])
                              for layer in ('NumericalOnly', 'TargetBounded')}
    elif reg['phase'] == 'repeatability':
        grouped = defaultdict(list)
        for entry in entries:
            entry['startup'] = 'reuse' if entry['worker'] == 'reuse-reset' else 'fresh'
            grouped[(entry['condition_id'],entry['startup'])].append(entry)
        if len(grouped) != 32 or any(len(g) != 3 for g in grouped.values()):
            raise ValueError('Repeatability requires 16 x 3 x 2 episodes')
        pair_details = []
        for (condition, startup), group in sorted(grouped.items()):
            for left,right in itertools.combinations(group,2):
                dirs = [directory/e['worker']/'episodes'/e['episode_id'] for e in (left,right)]
                frames = [records(p/'physics.jsonl.gz') for p in dirs]
                controls = [records(p/'controls.jsonl.gz') for p in dirs]
                initial = [read(p/'initial_capture.json') for p in dirs]
                fields = ('joint_position','joint_velocity','object_position','object_velocity','target_command')
                pair_details.append({'condition_id': condition, 'startup': startup,
                                     'episodes': [left['episode_id'],right['episode_id']],
                                     'initial_equal': all(initial[0][f] == initial[1][f] for f in fields),
                                     'first_physics_difference': first_difference(*frames,fields),
                                     'first_action_difference': first_difference(*controls,('accepted_raw_action','applied_target')),
                                     'instant_discordant': left['instant'] != right['instant'],
                                     'holding_discordant': left['holding'] != right['holding']})
        result['repeated_pairs'] = pair_details
        result['by_startup'] = {s: summarize([e for e in entries if e['startup'] == s]) for s in ('reuse','fresh')}
        result['repeatability'] = {s: {'pairs': sum(p['startup']==s for p in pair_details),
                                      'initial_mismatch_pairs': sum(p['startup']==s and not p['initial_equal'] for p in pair_details),
                                      'physics_divergence_pairs': sum(p['startup']==s and p['first_physics_difference'] is not None for p in pair_details),
                                      'instant_discordant_pairs': sum(p['startup']==s and p['instant_discordant'] for p in pair_details)}
                                   for s in ('reuse','fresh')}
        # Resample independent conditions, retaining their three repeats and
        # paired startup modes. This does not treat 96 rows as 96 iid samples.
        rng = random.Random(2026102604)
        conditions = sorted({e['condition_id'] for e in entries})
        differences = [sum(e['instant'] for e in grouped[(c,'fresh')])/3-
                       sum(e['instant'] for e in grouped[(c,'reuse')])/3 for c in conditions]
        boot = sorted(sum(rng.choices(differences,k=16))/16 for _ in range(10000))
        result['startup_instant_difference'] = {'fresh_minus_reuse': sum(differences)/16,
                                                'condition_bootstrap_interval': [boot[250],boot[9749]],
                                                'scope': 'conditional on fixed model, single GPU and one reused-process block; cannot isolate GPU contention or estimate process-population effects',
                                                'zero_width_warning': 'a degenerate empirical bootstrap is not proof of zero failure probability'}
    elif reg['phase'] == 'reachability':
        surface = {}
        for controller in ('Original','GeometryExpert','OpenGripper'):
            surface[controller] = {str(m): summarize([e for e in entries if e['worker']==controller and e['mass_kg']==m])
                                   for m in (.1,.4,.8,1.6)}
        references = [c for c in ('Original','GeometryExpert') if
                      all(surface[c][str(m)]['holding'] >= 2 for m in (.1,.4)) and
                      all(surface[c][str(m)]['hard_events'] == 0 for m in (.1,.4,.8,1.6))]
        negative_ok = not any(e['holding'] for e in entries if e['worker']=='OpenGripper')
        result['mass_surface'] = surface
        result['W3_gate'] = {'passed': bool(references) and negative_ok, 'qualified_references': references,
                             'negative_control_discrimination': negative_ok,
                             'next': 'preregister W4/W5 only after parameter-effect validation' if references and negative_ok else 'STOP actual W4/W5 learning comparison; calibrate controller/task in a new version'}
    with (directory/'episode_metrics.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(entries[0]))
        writer.writeheader()
        writer.writerows(entries)
    save_json(directory/'diagnosis.json',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True)
    args = parser.parse_args()
    value = report(args.run_dir)
    print(json.dumps({k:v for k,v in value.items() if k not in ('episodes','paired_cases','repeated_pairs')},indent=2))
