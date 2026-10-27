"""Independent object/release scoring and learning-run level summaries."""

import math


def place_metrics(initial,frames,control_dt=.02):
    if not frames or not math.isfinite(control_dt) or control_dt<=0:
        raise ValueError('Physical frames and positive interval required')
    origin=initial['object_position'][0]
    target=[origin[0]+.12,origin[1]+.12,.021]
    # The last post-physics sample of every control is the scoring sample.
    controls={f['control_step']:f for f in frames}
    if list(controls)!=list(range(len(controls))):
        raise ValueError('Continuous ordered control samples required')
    lifted=transported=False
    run=maximum=0
    first=None
    exited=False
    terminal=False
    for i,f in controls.items():
        obj=f['object_position'][0]
        speed=math.sqrt(sum(v*v for v in f['object_velocity'][0][:3]))
        lifted|=obj[2]-origin[2]>=.05
        transported|=math.dist(obj[:2],origin[:2])>=.08
        fingers=f['finger_position']
        terminal=(lifted and transported and math.dist(obj[:2],target[:2])<.05 and
                  abs(obj[2]-target[2])<.025 and speed<=.10 and min(fingers)>=.035 and
                  math.dist(f['ee_position_world'][0],obj)>=.06)
        run=run+1 if terminal else 0
        maximum=max(maximum,run)
        if run>0 and (run-1)*control_dt>=.5-1e-12 and first is None:
            first=(i+1)*control_dt
        if first is not None and not terminal:
            exited=True
    return {'schema':'core-place-score-1','success':first is not None,'lift_observed':lifted,
            'transport_observed':transported,'maximum_stable_span_s':max(0,maximum-1)*control_dt,
            'first_success_time_s':first,'terminal_eligible':terminal,'left_after_first_success':exited,
            'place_target_world':target,'scoring_samples':len(controls)}


def compare(initial,final):
    if set(initial)!=set(final) or not initial:
        raise ValueError('Paired nonempty heldout condition IDs required')
    n=len(initial)
    a,b=sum(initial.values()),sum(final.values())
    return {'initial_successes':a,'final_successes':b,'episodes_per_arm':n,
            'initial_rate':a/n,'final_rate':b/n,'gain':(b-a)/n,
            'statistical_scope':'One frozen learning artifact; paired conditions are not independent learning runs.'}
