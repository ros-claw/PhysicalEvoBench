"""Diagnostic only: distinguish GPU shadow parameters from PhysX model readback."""

import json

from physicalevobench.core import collect
from physicalevobench.core.native import CoreWorker
from physicalevobench.doctor import save_json

original_init=CoreWorker.__init__


def instrument(self,*args,**kwargs):
    original_init(self,*args,**kwargs)
    import warp as wp

    cube=self.base.scene['dex_cube']
    events=[]
    def read_model():
        return {'mass':self.as_torch(cube.root_view.get_masses()).tolist(),
                'inertia':self.as_torch(cube.root_view.get_inertias()).tolist()}
    for method,buffer,getter in [('set_masses_index','_cpu_body_mass','set_masses'),
                                  ('set_inertias_index','_cpu_body_inertia','set_inertias')]:
        original=getattr(cube,method)
        def observed(*a,_f=original,_name=method,_buffer=buffer,_setter=getter,**kw):
            before=read_model()
            result=_f(*a,**kw)
            immediately_after=read_model()
            # The CPU conversion of the GPU shadow itself synchronizes its transfer;
            # it cannot establish that the preceding PhysX setter consumed fresh CPU input.
            shadow={'mass':self.as_torch(cube.data.body_mass).tolist(),
                    'inertia':self.as_torch(cube.data.body_inertia).tolist()}
            after_shadow_read=read_model()
            if self.diag_cfg['diagnostic_sync_reapply']:
                wp.synchronize_device(self.base.device)
                ids=self.as_torch(kw['env_ids']).cpu().to(dtype=__import__('torch').int32).tolist()
                cpu_ids=wp.array(ids,dtype=wp.int32,device='cpu')
                values=getattr(cube,_buffer)
                if _setter=='set_inertias':
                    values=values.flatten()
                getattr(cube.root_view,_setter)(values,indices=cpu_ids)
            events.append({'method':_name,'before':before,'immediately_after':immediately_after,
                           'gpu_shadow':shadow,'after_shadow_read':after_shadow_read,
                           'after_optional_synchronized_reapply':read_model()})
            save_json(self.output_dir/'model_parameter_transport.json',events)
            print('ESL_MODEL_PARAMETER_TRANSPORT '+json.dumps(events[-1]),flush=True)
            return result
        setattr(cube,method,observed)
    from physicalevobench.core import readiness
    original_prepare=readiness.prepare
    def observed_prepare(worker):
        if worker is not self:
            return original_prepare(worker)
        save_json(self.ready_directory/'actual_model_before_probe.json',read_model())
        try:
            return original_prepare(worker)
        finally:
            save_json(self.ready_directory/'actual_model_after_probe.json',read_model())
    readiness.prepare=observed_prepare


CoreWorker.__init__=instrument

if __name__=='__main__':
    collect.main()
