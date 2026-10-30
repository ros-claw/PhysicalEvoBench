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
            if not all(b['scores'][a].get(key) is not None for a in ARMS):
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
        known=[v for v in values if v is not None]
        arms[a]={'name':LABELS[a],'successes':sum(known),'assigned':len(values),
                 'valid_task_executions':len(known),'missing':len(values)-len(known),
                 'successes_per_assigned':sum(known)/len(values) if values else None,
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
