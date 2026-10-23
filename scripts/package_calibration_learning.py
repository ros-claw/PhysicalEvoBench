"""Package every diagnostic attempt, raw evaluation trace and train transition chunk."""

import argparse
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

from physicalevobench.doctor import save_json, sha256


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=Path(a.output).absolute()
    out.mkdir(parents=True,exist_ok=False)
    runs=sorted((root/'runs').glob('calibration-*'))
    manifest=[]
    refs=set()
    for run in runs:
        config=run/'config.json'
        if config.exists():
            cfg=json.loads(config.read_text())
            refs.add(cfg['source_commit'])
            if 'supervisor_source_commit' in cfg:
                refs.add(cfg['supervisor_source_commit'])
        path=out/f'{run.name}.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            for item in sorted(run.rglob('*')):
                if item.is_file() and item.suffix not in {'.hdf5','.sock','.npz'}:
                    archive.add(item,arcname=str(item.relative_to(root/'runs')),recursive=False)
        manifest.append({'run':run.name,'archive':path.name,'sha256':sha256(path),
                         'status':json.loads((run/'status.json').read_text()) if (run/'status.json').exists() else
                         {'status':'SUPERVISOR_OR_STARTUP_FAILURE','physical_episodes':0}})
        chunks=sorted((run/'transitions').glob('*.npz'))
        for i in range(0,len(chunks),20):
            part=out/f'{run.name}-transitions-{i//20+1:02d}.tar.gz'
            with tarfile.open(part,'w:gz') as archive:
                for item in chunks[i:i+20]:
                    archive.add(item,arcname=str(item.relative_to(root/'runs')),recursive=False)
            manifest.append({'run':run.name,'archive':part.name,'sha256':sha256(part),'transition_chunks':len(chunks[i:i+20])})
    for ref in sorted(refs):
        target=out/f'source-{ref[:12]}.tar.gz'
        with target.open('wb') as stream:
            subprocess.run(['git','archive','--format=tar.gz',ref,'physicalevobench','scripts','configs',
                            'docs/experiments/CALIBRATION_LEARNING_PROTOCOL_20261023.md','LICENSE','NOTICE.md'],
                           cwd=root,stdout=stream,check=True)
    model=Path('/home/dell/models/physicalevobench/ppo-20261023-002')
    metadata=out/'model-metadata'
    metadata.mkdir()
    for name in ('training_losses.json','weight_change.json','params/agent.yaml'):
        target=metadata/Path(name).name
        shutil.copy2(model/name,target)
    save_json(out/'manifest.json',{'runs':manifest,'weights':'outside repository; not redistributed',
              'training_mode':'dense reward; no training success-rate equivalence to evaluation'})
    (out/'SHA256SUMS').write_text(''.join(f'{sha256(f)}  {f.relative_to(out)}\n' for f in sorted(out.rglob('*'))
                                      if f.is_file() and f.name!='SHA256SUMS'))
    print(out)


if __name__=='__main__':
    main()
