"""Reserved sequential physical tool sessions with immutable runtime sources."""

import concurrent.futures
import json
import time
from pathlib import Path

from physicalevobench.calibration.source_snapshot import snapshot_source
from physicalevobench.doctor import command, save_json
from physicalevobench.evaluation.confirmation import now
from physicalevobench.stability.study import launch


def atomic_json(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.pending')
    save_json(tmp,value)
    tmp.replace(path)


class NativeSession:
    def __init__(self,root,out,source_commit,cfg,gpu):
        self.out=Path(out)
        self.out.mkdir(parents=True,exist_ok=False)
        self.cfg=cfg
        self.used=0
        save_json(self.out/'config.json',cfg)
        save_json(self.out/'worker_reservation.json',{'maximum_episodes':cfg['physical_budget'],'at':now()})
        save_json(self.out/'gpu_workload.json',{'exclusive':False,'at':now(),'query':command(
            ['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv'])})
        source,hashes=snapshot_source(root,source_commit)
        save_json(self.out/'source_identity.json',{'commit':source_commit,'files':hashes})
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.future=self.pool.submit(launch,Path(root),source,self.out,'physicalevobench.core.collect',gpu)

    def _wait(self,path,timeout=600):
        deadline=time.monotonic()+timeout
        while not path.exists():
            if self.future.done():
                self.future.result()
                raise RuntimeError('Native session ended before response')
            if time.monotonic()>deadline:
                raise TimeoutError('Native response deadline exceeded')
            time.sleep(.25)
        while time.monotonic()<=deadline:
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                time.sleep(.05)
        raise TimeoutError('Native JSON response did not finish writing')

    def ready(self):
        return self._wait(self.out/'ready.json')

    def trial(self,job):
        if self.used>=self.cfg['physical_budget']:
            raise ValueError('Reserved physical session exhausted')
        i=self.used
        self.used+=1
        atomic_json(self.out/'requests'/f'{i:03d}.json',job)
        return self._wait(self.out/'responses'/f'{i:03d}.json')

    def close(self):
        atomic_json(self.out/'stop.json',{'at':now()})
        try:
            self.future.result(timeout=300)
        finally:
            self.pool.shutdown(wait=False)
