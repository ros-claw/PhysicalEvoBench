"""Train-only parameter search over a fixed guarded-controller family."""

import json
import random
import sys

from physicalevobench.agents.search_worker import select
from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.guarded_skill import GuardedSkill

OPTIONS = {
    'guard2': {'finger_guard_enabled':True,'finger_margin_m':.002},
    'hold10guard2': {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.002},
    'hold10guard6': {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.006},
    'hold10guard10look2': {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.01,'finger_lookahead_steps':2},
    'guard6look2': {'finger_guard_enabled':True,'finger_margin_m':.006,'finger_lookahead_steps':2},
    'hold10guard3look0': {'gripper_hold_steps':10,'finger_guard_enabled':True,'finger_margin_m':.003,'finger_lookahead_steps':0},
}


def respond(request):
    if set(request)!={'agent','rng_seed','history','remaining_budget'}:
        raise ValueError('Unknown guarded search fields')
    history=request['history']
    if request['agent'] not in {'feedback','random'} or not 1<=len(history)<=4:
        raise ValueError('Invalid guarded search history')
    if (type(request['rng_seed']) is not int or type(request['remaining_budget']) is not int
            or request['remaining_budget']<0):
        raise ValueError('Invalid guarded search RNG or budget')
    count=None
    for h in history:
        if set(h)!={'skill','feedback'}:
            raise ValueError('Unknown training trial fields')
        GuardedSkill.from_dict(h['skill'])
        values=[TrainingFeedback.from_payload(f) for f in h['feedback']]
        if not values or (count is not None and count!=len(values)):
            raise ValueError('Expected paired training feedback')
        count=len(values)
    trial=len(history)-1
    name=None
    if trial<3:
        if request['remaining_budget']<count:
            raise ValueError('Insufficient physical training budget')
        if request['agent']=='random':
            name=random.Random(request['rng_seed']).sample(list(OPTIONS),3)[trial]
        elif trial<2:
            name=('hold10guard10look2','hold10guard6')[trial]
        else:
            scores=[sum(f['success'] for f in h['feedback']) for h in history]
            name='hold10guard2' if scores[1]>=scores[2] else 'guard6look2'
    skill=GuardedSkill(history[0]['skill']['base_checkpoint_sha256'],skill_version=trial+1,
                       **OPTIONS[name]) if name else None
    return {'next_skill':skill.to_dict() if skill else None,'next_gain':None,
            'selected_index':select(history),'candidate_name':name,
            'source_failure_ids':[f['episode_id'] for h in history for f in h['feedback'] if not f['success']]}


def main():
    try:
        print(json.dumps(respond(json.load(sys.stdin)),allow_nan=False))
        return 0
    except (ValueError,TypeError,KeyError) as error:
        print(str(error),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
