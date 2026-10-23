"""Paired summaries conditional on one frozen learned snapshot."""

import random

from physicalevobench.evaluation.confirmation_stats import exact_p


def paired_statistics(rows):
    indexed={a:{r['condition_id']:r for r in rows if r['agent_id']==a} for a in ('original','candidate')}
    if indexed['original'].keys()!=indexed['candidate'].keys():
        raise ValueError('Unpaired learned-policy results')
    delta=[int(indexed['candidate'][k]['success'])-int(indexed['original'][k]['success']) for k in indexed['original']]
    rng=random.Random(20261022)
    boot=sorted(sum(rng.choices(delta,k=len(delta)))/len(delta) for _ in range(10000))
    return {'pairs':len(delta),'wins':delta.count(1),'losses':delta.count(-1),
            'success_rate_difference':sum(delta)/len(delta),
            'conditional_bootstrap_95':[boot[250],boot[9750]],
            'p_one_sided_exact':exact_p(delta.count(1),delta.count(-1)),
            'scope':'one learned snapshot; condition-level inference, no cross-learning-seed claim'}


