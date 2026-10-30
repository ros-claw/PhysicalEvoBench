"""Reviewable actual observation -> proposal -> trial -> freeze timeline."""

import argparse
import json
from pathlib import Path

from physicalevobench.core.artifact import load
from physicalevobench.core.program import Program
from physicalevobench.development.place import starter_program
from physicalevobench.doctor import save_json


def read(path):
    return json.loads(Path(path).read_text())


def summarize(root):
    output = []
    for instance in sorted(root.glob('instance-*')):
        for name in ('designer', 'feedback'):
            directory = instance/name
            history = read(directory/'history.json') if (directory/'history.json').exists() else []
            current = starter_program().to_dict()
            events = []
            for i, path in enumerate(sorted(directory.glob('proposal-*.json'))):
                proposal = read(path)
                request = read(directory/'model_calls'/f'call-{i:02d}'/'request.json')
                try:
                    candidate = Program.from_dict(json.loads(proposal['program_json']))
                except (ValueError, KeyError, TypeError):
                    events.append({'call': i, 'status': 'invalid_program'})
                    continue
                before = {n['id']: n for n in current['nodes']}
                after = {n['id']: n for n in candidate.nodes}
                changes = {}
                for key in sorted(set(before)|set(after)):
                    if before.get(key) != after.get(key):
                        changes[key] = {'before': before.get(key), 'after': after.get(key)}
                observed = [h.get('feedback', {}) for h in request['history'] if h.get('feedback')]
                event = {'call': i, 'tool': proposal['tool'], 'practice_handle': proposal['practice_handle'],
                         'program_hash': candidate.sha256, 'semantic_node_changes': changes,
                         'physical_outcomes_observed_before_proposal': [f['success'] for f in observed],
                         'participant_memory': proposal['memory'],
                         'usage': read(directory/'model_calls'/f'call-{i:02d}'/'usage.json')}
                if i < len(history) and history[i].get('feedback'):
                    f = history[i]['feedback']
                    event['actual_trial_outcome'] = {k: v for k, v in f.items() if k != 'events_and_periodic_samples'}
                events.append(event)
                current = candidate.to_dict()
            artifact = load(directory/'artifact.json') if (directory/'artifact.json').exists() else None
            output.append({'learning_instance': instance.name, 'method': name, 'events': events,
                           'frozen_artifact_hash': artifact['effective_artifact_hash'] if artifact else None,
                           'physical_practice_used': artifact['payload']['budget_used'] if artifact else None})
    value = {'schema': 'actual-learning-event-summary-1', 'methods': output,
             'scope': 'Derived from actual provider requests/responses and returned physical feedback; participant memory is a hypothesis, not evaluator truth. No additional model or physical calls.'}
    save_json(root/'learning_events.json', value)
    return value


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    a = p.parse_args()
    result = summarize(Path(a.run_dir))
    print(json.dumps({'methods': len(result['methods'])}))


if __name__ == '__main__':
    main()
