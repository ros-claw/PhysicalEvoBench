"""Paired conditions within cells, independent learning blocks as outer unit."""

import random
import statistics

ARMS=('frozen','designer','search','feedback','deletion')
LABELS={'frozen':'Frozen','designer':'NoFeedback','search':'TemplateSearch-4',
        'feedback':'Feedback','deletion':'Deletion'}


def interval(values):
    values=sorted(values)
    return [values[int(.025*(len(values)-1))],values[int(.975*(len(values)-1))]]


def comparison(blocks,baseline,draws=10000):
    points=[]
    cell_deltas=[]
    for b in blocks:
        cells={}
        for c in b['conditions']:
            key=c['condition_id']
            if not all(b['scores'][a].get(key) is not None and
                       b.get('execution_statuses',{}).get(a,{}).get(key,'OK')=='OK' for a in ARMS):
                continue
            cell=(tuple(c['public_goal']),c['object_mass_kg'])
            delta=int(b['scores']['feedback'][key])-int(b['scores'][baseline][key])
            cells.setdefault(cell,[]).append(delta)
        point=statistics.mean([v for values in cells.values() for v in values]) if cells else None
        points.append({'block':b['block'],'paired_valid_conditions':sum(map(len,cells.values())),
                       'feedback_minus_baseline':point})
        cell_deltas.append(list(cells.values()))
    # Incomplete blocks stay visible; do not manufacture a population interval.
    complete=all(p['paired_valid_conditions']==len(b['conditions']) for p,b in zip(points,blocks,strict=True))
    result={'baseline':baseline,'block_points':points,'all_blocks_complete':complete,
            'mean_block_effect':statistics.mean(p['feedback_minus_baseline'] for p in points) if complete else None,
            'hierarchical_95_interval':None,'unit':'independent learning block, paired condition within goal/mass cell'}
    if len(blocks)<2 or not complete:
        result['interval_status']='NOT_ESTIMATED: fewer than two independent complete blocks or missing executions'
        return result
    rng=random.Random(2026103032)
    samples=[]
    for _ in range(draws):
        outer=[]
        for _ in blocks:
            cells=rng.choice(cell_deltas)
            outer.append(statistics.mean(statistics.mean(rng.choices(cell,k=len(cell))) for cell in cells))
        samples.append(statistics.mean(outer))
    result.update(hierarchical_95_interval=interval(samples),interval_status='block-outer cell-stratified paired bootstrap')
    return result


def summarize(blocks):
    arms={}
    for a in ARMS:
        values=[b['scores'][a].get(c['condition_id']) for b in blocks for c in b['conditions']]
        statuses=[b.get('execution_statuses',{}).get(a,{}).get(c['condition_id'],'OK') for b in blocks for c in b['conditions']]
        known=[v for v,s in zip(values,statuses,strict=True) if v is not None and s=='OK']
        successes=sum(v is True for v in values)
        arms[a]={'name':LABELS[a],'successes':successes,'assigned':len(values),
                 'valid_task_executions':len(known),'missing':sum(v is None for v in values),
                 'participant_invalid':statuses.count('PARTICIPANT_INVALID'),'init_invalid':statuses.count('INIT_INVALID'),
                 'successes_per_assigned':successes/len(values) if values else None,
                 'valid_execution_success_rate':sum(known)/len(known) if known else None}
    discordances=[]
    for b in blocks:
        pairs=[(b['scores']['frozen'].get(c['condition_id']),b['scores']['deletion'].get(c['condition_id'])) for c in b['conditions']]
        pairs=[(x,y) for x,y in pairs if x is not None and y is not None]
        discordances.append({'block':b['block'],'paired_valid':len(pairs),
                            'frozen_only_success':sum(x and not y for x,y in pairs),
                            'deletion_only_success':sum(y and not x for x,y in pairs),
                            'discordant_pairs':sum(x!=y for x,y in pairs)})
    return {'arms':arms,'identity_replays':discordances,
            'comparisons':{a:comparison(blocks,a) for a in ('designer','deletion','search')},
            'scope':'Budget-cap comparisons; no matched tokens/FLOPs or isolated causal feedback claim; same finite physical problem.'}


def execution_chain(native,rows):
    """Count observable within-trajectory control effects, not a causal counterfactual."""
    from physicalevobench.v02.audit import records
    total={'GUARD_EVALUATED':0,'BRANCH_TAKEN':0,'GUARD_BRANCH':0,'TIMEOUT_BRANCH':0,
           'COMMAND_CHANGED':0,'APPLIED_TARGET_CHANGED':0}
    example=None
    for row in rows:
        if row['execution_status']!='OK':
            continue
        episode=native/'episodes'/row['episode_id']
        trace=records(native/row['trace_artifact'])
        controls=records(episode/'controls.jsonl.gz')
        for i,(t,c) in enumerate(zip(trace,controls,strict=True)):
            d=t['policy_diagnostics']
            guard=d.get('evaluator_guard')
            if not guard or not guard.get('guard_evaluated'):
                continue
            total['GUARD_EVALUATED']+=1
            if not guard['branch_taken']:
                continue
            total['BRANCH_TAKEN']+=1
            total['TIMEOUT_BRANCH' if guard['reason']=='bounded_node_timeout' else 'GUARD_BRANCH']+=1
            if i==0:
                continue
            previous=trace[i-1]['policy_diagnostics']['decision']
            command=d['decision']
            changed=(previous['target_position']!=command['target_position'] or previous['gripper']!=command['gripper'])
            if not changed:
                continue
            total['COMMAND_CHANGED']+=1
            applied=max(abs(a-b) for a,b in zip(c['applied_target'],controls[i-1]['applied_target'],strict=True))>1e-8
            if applied:
                total['APPLIED_TARGET_CHANGED']+=1
                if example is None:
                    example={'episode_id':row['episode_id'],'control_step':i,'guard':guard,
                             'previous_command':previous,'command':command,
                             'previous_applied_target':controls[i-1]['applied_target'],'applied_target':c['applied_target']}
    return {'counts':total,'example':example,
            'scope':'Nested real guard/branch/command/applied-target chain in recorded trajectories; does not isolate causation from state motion or prove improvement.'}
