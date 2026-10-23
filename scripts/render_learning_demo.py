"""Caption actual camera replays, explicitly marking padded terminal frames."""

import argparse
import subprocess
from pathlib import Path

from physicalevobench.calibration.audit import lines
from physicalevobench.doctor import save_json, sha256


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    a=p.parse_args()
    root=Path(a.run_dir).absolute()
    rows={r['agent_id']:r for r in lines(root/'episodes.jsonl')}
    left,right=(root/rows[k]['video_artifact'] for k in ('original','candidate'))
    duration=max(r['simulated_seconds'] for r in rows.values())
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    parts=[]
    for i,key in enumerate(('original','candidate')):
        r=rows[key]
        seconds=r['simulated_seconds']
        label=('Original' if key=='original' else 'PPO learned')+' - '+('SUCCESS' if r['success'] else 'TIMEOUT')
        filt=(f'[{i}:v]scale=336:336:flags=neighbor,tpad=stop_mode=clone:stop_duration={duration-seconds},'
              f'pad=336:436:0:50:black,drawtext=fontfile={font}:text={label}:x=8:y=10:fontsize=18:fontcolor=white,'
              f'drawtext=fontfile={font}:text=Post-hoc demo - 2.890 kg:x=8:y=400:fontsize=16:fontcolor=white')
        if duration>seconds:
            filt+=(f',drawtext=fontfile={font}:text=SIM ENDED - FRAME HELD:x=8:y=370:'
                   f'fontsize=16:fontcolor=yellow:enable=gte(t\\,{seconds})')
        parts.append(filt+f'[side{i}]')
    parts.append('[side0][side1]hstack=inputs=2[v]')
    output=root/'videos/learned_vs_original.mp4'
    output.parent.mkdir(exist_ok=True)
    argv=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(left),'-i',str(right),
          '-filter_complex',';'.join(parts),'-map','[v]','-t',str(duration),'-c:v','libx264',
          '-pix_fmt','yuv420p',str(output)]
    result=subprocess.run(argv,capture_output=True,text=True)
    save_json(root/'videos/render_receipt.json',{'argv':argv,'returncode':result.returncode,
              'stderr':result.stderr,'inputs':{str(f.relative_to(root)):sha256(f) for f in (left,right)},
              'output_sha256':sha256(output) if output.exists() else None,
              'scope':'actual wrist-camera video; successful branch final frame is held only in video, not in physics'})
    result.check_returncode()


if __name__=='__main__':
    main()
