"""Fence GPU-to-pinned-CPU parameter copies before PhysX consumes them.

Only the single Cube view is wrapped; pinned Arena/Lab source stays untouched.
The indexed setters, sampled values and inertia scaling remain upstream's own.
"""

import math


def flat(value):
    return [v for x in value for v in (flat(x) if isinstance(x,list) else [x])]


def validate(shadow,model,requested):
    if model.get('status')!='MEASURED':
        return False,'necessary_physx_model_readback_unavailable'
    for key,tolerance in [('mass',1e-6),('inertia',1e-10)]:
        a,b=flat(shadow[key]),flat(model[key])
        if len(a)!=len(b) or not a or any(not math.isfinite(x) or not math.isfinite(y) or
                                         abs(x-y)>tolerance+1e-6*abs(x) for x,y in zip(a,b,strict=True)):
            return False,'physx_model_shadow_mismatch:'+key
    masses=flat(model['mass'])
    inertia=flat(model['inertia'])
    if len(masses)!=1 or abs(masses[0]-requested)>1e-6:
        return False,'physx_model_requested_mass_mismatch'
    if len(inertia)!=9 or any(inertia[i]<=0 for i in (0,4,8)):
        return False,'physx_model_inertia_not_positive'
    return True,'physx_model_parameters_verified'


def read(worker):
    try:
        cube=worker.base.scene['dex_cube']
        return {'status':'MEASURED','source':'PhysX RigidBodyView.get_masses/get_inertias; independent of GPU shadow',
                'mass':worker.as_torch(cube.root_view.get_masses()).tolist(),
                'inertia':worker.as_torch(cube.root_view.get_inertias()).tolist()}
    except (AttributeError,RuntimeError,TypeError) as error:
        return {'status':'not_measured','reason':str(error)[:200]}


def install(worker):
    import warp as wp

    view=worker.base.scene['dex_cube'].root_view
    if view.count!=1:
        raise ValueError('Parameter handoff profile is qualified only for the single Cube view')
    for name in ('set_masses','set_inertias'):
        original=getattr(view,name)
        def fenced(*args,_f=original,**kwargs):
            # Upstream indexed setters enqueue wp.copy into pinned host buffers.
            # A CPU PhysX call must not consume those buffers or index scratch early.
            wp.synchronize_device(worker.base.device)
            return _f(*args,**kwargs)
        setattr(view,name,fenced)
