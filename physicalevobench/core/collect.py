"""Persistent native tool server, started only from immutable reserved source."""

import argparse
import gzip
import json
import shutil
import time
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.confirmation import now


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    out=Path(p.parse_args().run_dir)
    cfg=json.loads((out/'config.json').read_text())
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app=get_isaaclab_arena_cli_parser().parse_args(['--device','cuda:0'])
    with SimulationAppContext(app):
        from physicalevobench.protocols.skill import SkillSpec
        from physicalevobench.core.native import CoreWorker
        from physicalevobench.v02.reference_native import StateBasedReference

        if sha256(cfg['checkpoint_path'])!=cfg['checkpoint_sha256']:
            raise ValueError('Immutable checkpoint changed')
        shutil.copyfile(Path(cfg['checkpoint_path']).parent/'params/agent.yaml',out/'policy_config.yaml')
        worker=CoreWorker(cfg['checkpoint_path'],out,cfg)
        if cfg.get('initialization_diagnostic'):
            from physicalevobench.core.scene_diagnostics import install
            install(worker)
        (out/'episodes.jsonl').touch()
        save_json(out/'ready.json',{'at':now()})
        completed=[]
        try:
            for i in range(cfg['physical_budget']):
                request=out/'requests'/f'{i:03d}.json'
                deadline=time.monotonic()+600
                while not request.exists():
                    if (out/'stop.json').exists():
                        save_json(out/'status.json',{'status':'COMPLETED','episodes':len(completed),'unused_budget':cfg['physical_budget']-len(completed)})
                        return
                    if time.monotonic()>deadline:
                        raise TimeoutError('No reserved participant trial arrived')
                    time.sleep(.2)
                job=json.loads(request.read_text())
                save_json(out/'reservations'/f'{i:03d}.json',{'at':now(),'job':job})
                if 'public_goal' in job:
                    worker.diag_cfg['public_goal']=job['public_goal']
                if job.get('program'):
                    from physicalevobench.core.native import ProgramReference
                    worker.policy=ProgramReference(worker,cfg['reference_config'],job['program'])
                else:
                    worker.policy=StateBasedReference(worker,job['reference_config'])
                if job.get('diagnostic_hold'):
                    from physicalevobench.core.scene_diagnostics import HoldReference
                    worker.policy=HoldReference(worker)
                if job.get('force_open'):
                    from physicalevobench.v02.reference_native import OpenReference
                    worker.policy=OpenReference(worker.policy,worker.action_mapping['gripper_action']['start'])
                get_action=worker.policy.get_action

                def proposed(env,obs):
                    action=get_action(env,obs)
                    worker.last_network_proposal=action.clone()
                    return action

                worker.policy.get_action=proposed
                row=worker.run_episode(job['condition'],SkillSpec(worker.checkpoint_hash),
                                       'core-participant',job['episode_id'])
                if cfg.get('initialization_diagnostic'):
                    save_json(out/'episodes'/job['episode_id']/'initialization_events.json',worker.initialization_events)
                    worker.initialization_events=[]
                trace=out/row['trace_artifact']
                with trace.open('rb') as src,gzip.open(str(trace)+'.gz','wb') as dst:
                    shutil.copyfileobj(src,dst)
                trace.unlink()
                row['trace_artifact']+='.gz'
                row['trace_sha256']=sha256(out/row['trace_artifact'])
                row['core_identity']=job['identity']
                if cfg.get('core_task')=='place':
                    from physicalevobench.core.metrics import place_metrics
                    row['place']=place_metrics(worker.initial_capture,worker.frames,goal=job.get('public_goal'))
                    row['success']=row['place']['success']
                    row['failure_type']=None if row['success'] else 'place_task_not_completed'
                save_json(out/'episodes'/job['episode_id']/'episode.json',row)
                completed.append(row)
                (out/'episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in completed))
                save_json(out/'responses'/f'{i:03d}.json',row)
            save_json(out/'status.json',{'status':'COMPLETED','episodes':len(completed)})
        finally:
            save_json(out/'server_receipt.json',{'completed':len(completed),'at':now()})
            worker.close()


if __name__=='__main__':
    main()
