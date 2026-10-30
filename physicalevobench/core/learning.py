"""Executable-skill learning pilot with an actual same-model no-feedback control.

Evaluator manifests stay in the parent. Only public goal handles and measured
observations cross the JSON participant boundary. Test uses frozen programs only.
"""

import argparse
import json
import random
import uuid
from pathlib import Path

from physicalevobench.core.artifact import freeze, load as load_artifact
from physicalevobench.core.audit import assert_public, audit_session
from physicalevobench.core.metrics import compare
from physicalevobench.core.model import ParticipantProcess
from physicalevobench.core.pilot import worker_config
from physicalevobench.core.program import GUARDS, MODES, NODE_FIELDS, TARGETS, Program
from physicalevobench.core.runtime import NativeSession
from physicalevobench.development.place import make_job, starter_program
from physicalevobench.doctor import command, save_json, sha256
from physicalevobench.evaluation.confirmation import now
from physicalevobench.evaluation.seed_registry import published_seeds, registered_seed_values
from physicalevobench.v02.audit import records
from physicalevobench.v02.reference_artifact import digest, load

SCHEMA = {'type': 'object', 'additionalProperties': False,
          'properties': {'tool': {'type': 'string', 'enum': ['run_trial', 'revise', 'freeze']},
                         'program_json': {'type': 'string'},
                         'practice_handle': {'type': 'string'},
                         'memory': {'type': 'string', 'maxLength': 4000}},
          'required': ['tool', 'program_json', 'practice_handle', 'memory']}

INSTRUCTIONS = '''You are an experimental participant in Executable-Skill Learning.
Use only this JSON context. No filesystem, shell, web or other built-in tools.
Fixed model and low-level IK/target bounds. You may edit a bounded skill graph;
there is no training of model weights. Test runs only the frozen executable graph.
Task: pick up the cube, lift at least .05m above reset height, move it horizontally
at least .08m, then release it near the public task goal. Within 20s, reach .50s
continuous samples with horizontal error<.05m, vertical error<.025m, object
speed<=.10m/s, BOTH actual finger coordinates>=.035m, EE/object distance>=.06m.
Public observations are simulator state: positions, object linear velocity, real
finger positions and measured finger/cube normal contact, orientation error.
Support contact is NOT measured. The public task_goal_position is distinct from
the legacy airborne goal_position. Every trial resets physical state and controller.
A normal existing pick/probe/place starter is supplied equally to all methods.
No developer reference solution or diagnostic hypothesis is supplied.
The graph schema is core-skill-graph-2, max16 nodes, max_retries 0..2, max64
transitions. Each node has exactly the listed fields. All edges must exist.
mode is a compatibility label: this execution profile enables bounded joint
integral by measured bilateral contact and smoothly unloads on contact loss;
mode/node names do not enable or disable that compensation.
Targets may use legacy public primitives, or {frame,offset_m,grasp_offset}.
frame: object, goal (public task goal), ee, anchor, initial_object. offset_m is a
3-vector in world axes, each in [-.2,.2]. grasp_offset bool adds measured EE/object
relative offset captured at grasp/probe. Gripper is open or close.
Guards may be legacy names, or a bounded public expression:
{observable,op,value}, op le/ge, or {all:[expressions]} / {any:[expressions]}, maxdepth3,
max4 children. Observable names: finger_min (0...05m), object_speed (0..2m/s),
goal_xy_error, goal_z_error, object_goal_error, ee_object_distance, target_error
(all0..1m), finger_contact_min/max (0..200N), orientation_error (0..3.2rad).
A guard must hold continuously for dwell_s [.02,.5]; minimum_s [0,1], timeout_s
[.1,20]. tolerance [.005,.06], offset_m legacy scalar [0,.15]. Timeouts also follow
edges; global horizon is fixed. No scoring/state mutation or arbitrary code.
Return only schema JSON. program_json contains the complete graph serialized as
JSON text. run_trial executes a registered proposal on the chosen practice handle;
revise records a proposal without physics; freeze selects the final legal graph
and memory. You may keep the starter or freeze early. No positive gain required.
The same physical mechanism recurs across positions/goals and reset conditions.
Query conditions are never returned for update. Only executable program changes
can affect test control; text memory is retained as provenance, not interpreted.
'''


def event_feedback(directory, row):
    trace = records(Path(directory)/row['trace_artifact'])
    indices = {0, len(trace)-1}
    previous = None
    for i, sample in enumerate(trace):
        node = sample['policy_diagnostics']['decision'].get('program_node')
        if node != previous:
            indices.update((max(0, i-1), i))
        previous = node
    indices.update(range(0, len(trace), 100))
    samples = []
    for i in sorted(indices):
        sample = trace[i]
        d = sample['policy_diagnostics']
        samples.append({'time_s': i*.02, 'node': d['decision'].get('program_node'),
                        'gripper': d['decision']['gripper'], 'target': d['target_position'],
                        **d['public']})
    controls = records(Path(directory)/'episodes'/row['episode_id']/'controls.jsonl.gz')
    return {'success': row['success'], 'cost_episodes': 1, 'controls': row['steps'],
            'hard_boundary': row['diagnostic']['hard_boundary_terminated'],
            'limited_control_steps': sum(bool(c['limited_joints']) for c in controls),
            'events_and_periodic_samples': samples}


def manifest(root, parent, instances):
    excluded = published_seeds(root)
    for path in parent.glob('peb-*/registration.json'):
        excluded.update(registered_seed_values(json.loads(path.read_text())))
    rng = random.Random(2026103004)
    groups = []
    for run in range(instances):
        group = {}
        for split, goals in [('support', [[.62, .12, .021], [.60, -.12, .021]]),
                              ('query', [[.58, .10, .021], [.64, -.08, .021]])]:
            group[split] = []
            for goal in goals:
                for mass in (.1, .4):
                    seed = rng.randrange(2**31)
                    while seed in excluded:
                        seed = rng.randrange(2**31)
                    excluded.add(seed)
                    group[split].append({'condition_id': f'instance-{run}-{split}-{len(group[split])}',
                                         'seed': seed, 'split': split, 'object_mass_kg': mass,
                                         'public_goal': goal})
        groups.append(group)
    return groups


def artifact(base, program, source, run_id, name, used, memory):
    return {'schema': 'core-artifact-1', 'track': 'S', 'participant': name,
            'interface': 'executable-skill-json-v2', 'executor': 'contact-integral-v1/'+source,
            'task': 'core-place-public-v3-dev', 'scoring': 'core-place-score-1',
            'initial_reference': digest(base), 'skill': program.to_dict(), 'memory': memory,
            'budget_used': used, 'learning_run_id': run_id}


def compact(history):
    value = json.loads(json.dumps(history))
    for item in value[:-1]:
        if item.get('feedback'):
            item['feedback'].pop('events_and_periodic_samples', None)
        item.pop('program', None)
    return value


def learn(root, out, source, cfg, base, group, name, model, provider, run_id, gpu):
    directory = out/name
    directory.mkdir()
    participant = ParticipantProcess(provider, model, directory/'model_calls',
                                     max_calls=10, input_limit=300000, output_limit=48000, schema=SCHEMA)
    feedback_enabled = name == 'feedback'
    session = None
    if feedback_enabled:
        session = NativeSession(root, directory/'native', source, cfg, gpu)
        session.ready()
    history, used = [], 0
    stage='participant'
    current = starter_program()
    try:
        for index in range(10):
            request = {'instructions': INSTRUCTIONS,
                       'method': 'Feedback Learner' if feedback_enabled else 'No-Feedback Designer',
                       'feedback_policy': ('Real physical observations after trials' if feedback_enabled else
                                           'No physical trials or observations available; use revise or freeze'),
                       'starter_program': starter_program().to_dict(), 'current_program': current.to_dict(),
                       'public_practice_handles': [{'handle': f'practice-{i}', 'public_goal': c['public_goal']}
                                                   for i, c in enumerate(group['support'])],
                       'legacy_targets': sorted(t for t in TARGETS if not t.startswith('place_')), 'legacy_guards': sorted(GUARDS),
                       'legacy_modes': sorted(MODES), 'node_fields': sorted(NODE_FIELDS),
                       'budget': {'max_calls': 10, 'calls_used': index, 'max_physical_episodes': 8,
                                  'physical_episodes_used': used, 'input_token_cap': 300000,
                                  'output_token_cap': 48000},
                       'history': compact(history)}
            assert_public(request)
            stage='participant'
            response = participant.call(request)
            save_json(directory/f'proposal-{index:02d}.json', response)
            try:
                if not isinstance(response,dict) or set(response)!={'tool','program_json','practice_handle','memory'}:
                    raise ValueError('Participant invalid fields')
                proposal=Program.from_dict(json.loads(response['program_json']))
                if proposal.schema!='core-skill-graph-2':
                    raise ValueError('Participant must use declared v2 graph')
                if not isinstance(response['memory'],str) or len(response['memory'])>4000:
                    raise ValueError('Invalid participant memory')
                tool=response['tool']
                if tool not in ('run_trial','revise','freeze'):
                    raise ValueError('Invalid participant tool')
                if tool=='run_trial' and (not feedback_enabled or used>=8):
                    raise ValueError('Physical trials unavailable for this method/budget')
                handles={f'practice-{i}':c for i,c in enumerate(group['support'])}
                if tool=='run_trial' and response['practice_handle'] not in handles:
                    raise ValueError('Invalid practice handle')
            except (ValueError,TypeError,KeyError) as error:
                history.append({'tool':'validation_error','error':str(error),'cost_episodes':0})
                save_json(directory/'history.json',history)
                continue
            current=proposal
            entry = {'tool': tool, 'program': current.to_dict(), 'program_hash': current.sha256}
            if tool == 'freeze':
                save_json(directory/'freeze_receipt.json',{'at':now(),'proposal_index':index,
                          'program_hash':current.sha256,'physical_episodes_used':used})
                return freeze(artifact(base, current, source, run_id, name, used, response['memory']),
                              directory/'artifact.json')
            if tool == 'run_trial':
                if not feedback_enabled or used >= 8:
                    raise ValueError('Unauthorized physical trial')
                handles = {f'practice-{i}': c for i, c in enumerate(group['support'])}
                if response['practice_handle'] not in handles:
                    raise ValueError('Invalid practice handle')
                job = make_job(current, handles[response['practice_handle']], f'learn-{used:03d}', name)
                job['reference_config'] = base['reference_config']
                job['identity'].update(learning_run_id=run_id, candidate_index=index)
                stage='physics'
                row = session.trial(job)
                stage='participant'
                used += 1
                entry['feedback'] = event_feedback(session.out, row)
            elif tool != 'revise':
                raise ValueError('Invalid participant tool')
            history.append(entry)
            save_json(directory/'history.json', history)
        raise ValueError('Participant failed to freeze within call budget')
    except Exception as error:
        if stage=='physics':
            raise
        save_json(directory/'validity_failure.json',{'status':'INVALID_PARTICIPANT_SUBMISSION',
                  'reason':str(error),'physical_episodes_used':used,'at':now(),
                  'query_scoring':'zero for every assigned query; retained in denominator'})
        return None
    finally:
        if session is not None:
            session.close()



def search_candidates():
    from physicalevobench.core.expressions import comparison
    values=[starter_program().to_dict() for _ in range(4)]
    # Fixed public proposal family, declared before support outcomes. Not an
    # exhaustive optimizer of the entire graph language.
    rng=random.Random(2026103005)
    for n in values[1]['nodes']:
        if n['id']=='release':
            n['guard']=comparison('finger_min','ge',rng.uniform(.035,.039))
            n['dwell_s']=.10
    for n in values[2]['nodes']:
        if n['id']=='lower':
            n['guard']={'all':[comparison('goal_xy_error','le',.035),
                               comparison('object_speed','le',rng.uniform(.08,.14))]}
            n['dwell_s']=.06
    for n in values[3]['nodes']:
        if n['id']=='release':
            n['minimum_s']=1.
    return [Program.from_dict(v) for v in values]


def score_search(root,directory,source,cfg,base,group,run_id,gpu):
    out=directory/'search'
    out.mkdir()
    programs=search_candidates()
    save_json(out/'candidate_registration.json',{'at':now(),
              'programs':[p.to_dict() for p in programs],
              'practice_indices':[0,1],'selection':'largest batch success count; stable earliest tie',
              'scope':'Four-program proposal family; same full legal space, narrower sampling prior'})
    session=NativeSession(root,out/'native',source,{**cfg,'physical_budget':8},gpu)
    scores=[]
    try:
        session.ready()
        for i,program in enumerate(programs):
            outcomes=[]
            for j,c in enumerate(group['support'][:2]):
                job=make_job(program,c,f'search-{i}-{j}','search')
                job['reference_config']=base['reference_config']
                row=session.trial(job)
                # Algorithm observes only the task score, never the trace.
                outcomes.append(bool(row['success']))
            scores.append(sum(outcomes))
    finally:
        session.close()
    selected=max(range(len(scores)),key=lambda i:scores[i])
    save_json(out/'selection.json',{'batch_scores':scores,'selected':selected,'at':now()})
    save_json(out/'freeze_receipt.json',{'at':now(),'program_hash':programs[selected].sha256})
    return freeze(artifact(base,programs[selected],source,run_id,'search',8,''),out/'artifact.json')

def run(root, out, qualification, reference, model, provider, instances, gpu):
    if command(['git', 'status', '--porcelain'], cwd=root)['stdout']:
        raise ValueError('Freeze implementation before learning registration')
    receipt = json.loads(qualification.read_text())
    if receipt.get('status') != 'QUALIFIED':
        raise ValueError('Task is not qualified; continue engineering, not model scaling')
    base = load(reference)
    source = command(['git', 'rev-parse', 'HEAD'], cwd=root)['stdout']
    from physicalevobench.core.execution_identity import validate_execution
    validate_execution(root,receipt,base)
    executor_source=source
    cfg = worker_config(base, 8)
    cfg.update(core_task='place', task_version='core-place-public-v3-dev', horizon_s=20.,
               control_profile='contact-integral-v1', public_goal=[.62, .12, .021])
    groups = manifest(root, out.parent, instances)
    out.mkdir(parents=True, exist_ok=False)
    study_id = str(uuid.uuid4())
    save_json(out/'registration.json', {'schema': 'esl-learning-1', 'mode': 'BENCHMARK_PILOT',
              'study_id': study_id, 'source_commit': executor_source, 'scheduler_source_commit':source,'at': now(), 'conditions': groups,
              'physical_budget': instances*(8+8+20), 'instances': instances, 'model': model,
              'model_limits_per_method': {'calls': 10, 'input_tokens': 300000, 'output_tokens': 48000},
              'qualification_sha256': sha256(qualification), 'qualification': receipt, 'gpu': gpu,
              'cfg': cfg, 'reference': base, 'provider': provider,
              'search': '4 declared candidates x same2 practice conditions; 8 trials, score only; limited proposal family',
              'scope': 'Paired pilot; independent model learning instances, not a stable-evolution proof'})
    save_json(out/'status.json', {'status': 'RUNNING'})
    all_artifacts = []
    for i, group in enumerate(groups):
        directory = out/f'instance-{i}'
        directory.mkdir()
        run_id = f'{study_id}/instance-{i}'
        artifacts = {}
        artifacts['frozen'] = freeze(artifact(base, starter_program(), executor_source, run_id,
                                             'frozen', 0, ''), directory/'frozen.json')
        for name in (['designer', 'feedback'] if i % 2 == 0 else ['feedback', 'designer']):
            artifacts[name] = learn(root, directory, executor_source, cfg, base, group, name, model, provider, run_id, gpu)
        artifacts['search']=score_search(root,directory,executor_source,cfg,base,group,run_id,gpu)
        artifacts['deletion'] = freeze(artifact(base, starter_program(), executor_source, run_id,
                                               'deletion', 0, ''), directory/'deletion.json')
        all_artifacts.append(artifacts)
    save_json(out/'all_frozen.json', {'at': now(), 'artifacts': [
        {n: (a['effective_artifact_hash'] if a is not None else 'INVALID_PARTICIPANT_SUBMISSION') for n, a in artifacts.items()} for artifacts in all_artifacts]})
    # No query execution until ALL methods / instances are frozen.
    for i, (group, artifacts) in enumerate(zip(groups, all_artifacts, strict=True)):
        for name in (['frozen', 'designer', 'search', 'feedback', 'deletion'] if i % 2 == 0 else
                     ['deletion', 'feedback', 'search', 'designer', 'frozen']):
            value = artifacts[name]
            if value is None:
                continue
            tc = {**cfg, 'physical_budget': len(group['query'])}
            session = NativeSession(root, out/f'instance-{i}'/f'test-{name}', executor_source, tc, gpu)
            try:
                session.ready()
                # Read and verify persisted artifact, not the learner's live object.
                path = out/f'instance-{i}'/(f'{name}.json' if name in ('frozen', 'deletion') else f'{name}/artifact.json')
                restored = load_artifact(path)
                program = Program.from_dict(restored['payload']['skill'])
                for j, c in enumerate(group['query']):
                    job = make_job(program, c, f'query-{j:03d}', name)
                    job['reference_config'] = base['reference_config']
                    job['identity'].update(effective_artifact_hash=value['effective_artifact_hash'],
                                           learning_run_id=value['payload']['learning_run_id'])
                    session.trial(job)
            finally:
                session.close()
    result = summarize(out)
    save_json(out/'status.json', {'status': 'COMPLETED', 'at': now()})
    print(json.dumps(result, indent=2))


def summarize(out):
    reg = json.loads((out/'registration.json').read_text())
    frozen = json.loads((out/'all_frozen.json').read_text())
    from physicalevobench.core.learning_audit import audit_bindings
    binding=audit_bindings(out,reg,frozen)
    results = []
    episodes = controls = samples = 0
    for i in range(reg['instances']):
        directory = out/f'instance-{i}'
        scores = {}
        for name in ('frozen', 'designer', 'search', 'feedback', 'deletion'):
            test = directory/f'test-{name}'
            if name in ('designer','feedback') and (directory/name/'validity_failure.json').exists():
                scores[name]={c['condition_id']:False for c in reg['conditions'][i]['query']}
                continue
            if json.loads((test/'launch.json').read_text())['started_at'] <= frozen['at']:
                raise ValueError('Test before global freeze')
            rows = audit_session(test)
            scores[name] = {r['condition_id']: r['success'] for r in rows}
            episodes += len(rows)
            controls += sum(r['steps'] for r in rows)
            samples += sum(r['diagnostic']['physics_samples'] for r in rows)
        for training_name in ('feedback','search'):
            train=directory/training_name/'native'
            if train.exists():
                rows=audit_session(train)
                episodes+=len(rows)
                controls+=sum(r['steps'] for r in rows)
                samples+=sum(r['diagnostic']['physics_samples'] for r in rows)
        cost = {}
        for name in ('designer', 'feedback'):
            for request in (directory/name/'model_calls').glob('call-*/request.json'):
                assert_public(json.loads(request.read_text()))
            budgets=directory/name/'model_calls/budget.json'
            cost[name]=json.loads(budgets.read_text()) if budgets.exists() else {'status':'usage_unknown'}
        results.append({'learning_instance': i, 'scores': scores, 'model_cost': cost,'participant_validity':{n:('INVALID' if (directory/n/'validity_failure.json').exists() else 'VALID') for n in ('designer','feedback')},
                        'feedback_gain': compare(scores['designer'], scores['feedback']),
                        'artifact_gain': compare(scores['deletion'], scores['feedback']),
                        'designer_gain': compare(scores['frozen'], scores['designer'])})
    if episodes > reg['physical_budget']:
        raise ValueError('Registered physical budget exceeded')
    from physicalevobench.stability.metrics import paired_interval
    intervals={}
    for key, baseline in [('feedback_gain','designer'),('artifact_gain','deletion')]:
        paired=[[int(item['scores']['feedback'][c])-int(item['scores'][baseline][c])
                 for c in item['scores']['feedback']] for item in results]
        intervals[key]=paired_interval(paired)
    result = {'binding_audit':binding,'paired_conditional_intervals':intervals,'schema': 'esl-learning-results-1', 'audit': 'PASS', 'instances': results,
              'physical_episodes': episodes, 'controls': controls, 'physics_samples': samples,
              'search': 'COMMON_BATCH_4x2', 'transfer': 'NOT_RUN', 'retention': 'NOT_RUN',
              'scope': 'Small adaptation pilot; zero/negative effects retained, no stability claim'}
    save_json(out/'results.json', result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--qualification', required=True)
    p.add_argument('--reference', default='configs/core/frozen_reference.json')
    p.add_argument('--model', default='gpt-6.1-terra')
    p.add_argument('--provider', help='JSON argv; omit for existing Codex transport')
    p.add_argument('--instances', type=int, default=2, choices=[1, 2])
    p.add_argument('--gpu', type=int, default=2)
    a = p.parse_args()
    run(Path.cwd(), Path(a.output).absolute(), Path(a.qualification), Path(a.reference),
        a.model, json.loads(a.provider) if a.provider else ['codex'], a.instances, a.gpu)


if __name__ == '__main__':
    main()
