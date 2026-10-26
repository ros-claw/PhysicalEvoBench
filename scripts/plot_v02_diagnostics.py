"""Standalone source-backed research figures for local diagnostic documents.

Run with the pinned Arena interpreter (matplotlib), not SimulationApp. No GPU
episodes are launched. Plot source and exact episode rows remain inspectable.
"""

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read
from physicalevobench.v02.audit import audit_run, records


BLUE, GOLD, GREY = '#235789', '#a66d00', '#5a6066'


def magnitude(value):
    if value is None:
        return math.nan
    if isinstance(value[0], list):
        return max(magnitude(v) for v in value)
    return math.sqrt(sum(v*v for v in value))


def timeline(run, worker_name, output):
    worker = run/worker_name
    row = read(worker/'config.json')
    episode = worker/'episodes'/row['jobs'][0]['episode_id']
    row = read(episode/'episode.json')
    meta = read(worker/'control_semantics.json')
    initial = read(episode/'initial_capture.json')
    first = row['diagnostic']['first_violation']
    if first is None:
        raise ValueError('Select a recorded first-violation episode')
    frames = records(episode/'physics.jsonl.gz')
    controls = records(episode/'controls.jsonl.gz')
    frames = [f for f in frames if -.2 <= (f['physics_step_global']-first['physics_step_global'])*meta['physics_dt'] <= .15]
    x = [(f['physics_step_global']-first['physics_step_global'])*meta['physics_dt'] for f in frames]
    colors = [BLUE, GOLD]
    fingers = [i for i,n in enumerate(meta['joint_names']) if 'finger' in n]
    arms = [i for i,n in enumerate(meta['joint_names']) if 'finger' not in n]
    fig, axes = plt.subplots(6, 1, figsize=(10, 13), sharex=True, layout='constrained')
    axes[0].plot(x, [max(abs(v) for v in controls[f['control_step']]['network_proposal'][0][:7]) for f in frames], color=BLUE)
    axes[0].set_ylabel('Max |arm raw action|\n(policy units)')
    for key,style,label,color in [('processed_target','--','Processed arm target',GOLD),
                                  ('applied_target','-','Applied arm target',BLUE)]:
        axes[1].plot(x,[max(abs(controls[f['control_step']][key][j]) for j in arms) for f in frames],
                     style,color=color,label=label)
    axes[1].set_ylabel('Max |arm target|\n(rad)')
    axes[0].set_ylim(bottom=0)
    axes[1].set_ylim(bottom=0)
    axes[1].legend(loc='upper left',fontsize=9)
    for k,j in enumerate(fingers):
        axes[2].plot(x,[f['joint_position'][0][j] for f in frames], color=colors[k],label=f'Finger {k+1} state')
        axes[2].plot(x,[controls[f['control_step']]['applied_target'][j] for f in frames], '--', color=colors[k],label=f'Finger {k+1} target')
        axes[3].plot(x,[f['joint_velocity'][0][j] for f in frames],color=colors[k],label=f'Finger {k+1}')
    axes[2].axhline(0,color=GREY,lw=.8)
    axes[2].axhline(.04,color=GREY,lw=.8)
    axes[2].set_ylabel('Finger position\n(m)')
    axes[2].legend(loc='lower left',fontsize=8,ncol=2)
    axes[3].axhline(meta['solver_velocity_limits'][fingers[0]],color=GREY,lw=.8,ls=':')
    axes[3].axhline(-meta['solver_velocity_limits'][fingers[0]],color=GREY,lw=.8,ls=':')
    axes[3].set_ylabel('Finger velocity\n(m/s; dotted: live limit)')
    for field,label,style,color in [('net_force_w','Max finger net force','-',BLUE),
                                    ('cube_force_matrix_w','Max finger cube-filtered force','--',GOLD)]:
        axes[4].plot(x,[max(magnitude(f['contacts'][side][field]['value']) for side in ('left','right')) for f in frames],
                     style,color=color,label=label)
    axes[4].set_ylabel('Contact force\n(N)')
    axes[4].set_ylim(bottom=0)
    axes[4].legend(loc='upper left',fontsize=8)
    depths = [1000*max(max(meta['hard_limits'][j][0]-f['joint_position'][0][j],
                           f['joint_position'][0][j]-meta['hard_limits'][j][1],0) for j in fingers) for f in frames]
    axes[5].plot(x,depths,color=BLUE)
    axes[5].axhline(1,color=GREY,lw=.8,ls=':',label='1 mm measurement threshold')
    axes[5].axhline(10,color=GREY,lw=.8,ls='--',label='10 mm severe boundary')
    axes[5].set_ylabel('Max finger depth\n(mm)')
    axes[5].set_ylim(bottom=0)
    axes[5].legend(loc='upper left',fontsize=8)
    axes[5].set_xlabel('Time relative to first measured >1 mm violation (s)')
    for ax in axes:
        ax.axvline(0,color=GREY,lw=.8)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15)
        ax.tick_params(labelsize=9)
    state = read(episode/'initial_state.json')['condition']
    t = (first['physics_step_global']-initial['physics_step_global'])*meta['physics_dt']
    fig.suptitle(f'{worker_name} | mass {state["object_mass_kg"]:.3f} kg | seed {state["seed"]}\n'
                 f'First violation t={t:.3f}s; 5 ms samples; selected diagnostic case, n=1',fontsize=12)
    fig.savefig(output,dpi=150)
    plt.close(fig)
    return {'figure':output.name,'episode':str(episode),'episode_sha256':sha256(episode/'episode.json'),
            'raw_files':{n:sha256(episode/n) for n in ('controls.jsonl.gz','physics.jsonl.gz')},
            'scope':'Recorded samples connected for readability; simultaneous telemetry is not unique causal attribution'}


def surface(run, output):
    result = read(run/'diagnosis.json')
    data = result['mass_surface']
    names = ['Original','GeometryExpert','OpenGripper']
    masses = ['0.1','0.4','0.8','1.6']
    fields = [('instant','Instant arrivals / 3',3),('holding','Effective holds / 3',3),
              ('maximum_holding_span_s','Maximum hold span (s)',5),('maximum_finger_depth_m','Max finger depth (mm)',None)]
    fig, axes = plt.subplots(1,4,figsize=(16,4),layout='constrained')
    for ax,(field,title,high) in zip(axes,fields,strict=True):
        matrix = [[data[n][m][field]*(1000 if field=='maximum_finger_depth_m' else 1) for m in masses] for n in names]
        high = high if high is not None else max(10,max(max(row) for row in matrix))
        image = ax.imshow(matrix, vmin=0,vmax=high,cmap='Blues',aspect='auto')
        for i,row in enumerate(matrix):
            for j,v in enumerate(row):
                ax.text(j,i,f'{v:.2f}' if field not in ('instant','holding') else str(int(v)),ha='center',va='center',color='white' if v>high*.6 else '#202328')
        ax.set_xticks(range(4),masses)
        ax.set_yticks(range(3),names)
        ax.set_xlabel('Object mass (kg)')
        ax.set_title(title,fontsize=11)
        fig.colorbar(image,ax=ax,shrink=.65)
    fig.suptitle('FixedHorizonDiagnostic, common TargetBounded executor: 3 development seeds per cell\n'
                 'Selected small calibration grid; counts/spans are observations, not population estimates',fontsize=12)
    fig.savefig(output,dpi=150)
    plt.close(fig)
    return {'figure':output.name,'diagnosis_sha256':sha256(run/'diagnosis.json')}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    p.add_argument('--output-dir',required=True)
    a = p.parse_args()
    run,out=Path(a.run_dir),Path(a.output_dir)
    audit_run(run)
    out.mkdir(parents=True,exist_ok=True)
    if read(run/'registration.json')['phase']=='representatives':
        receipt=[timeline(run,name,out/(name+'.png')) for name in
                 ('sample-00-NumericalOnly','sample-00-TargetBounded','sample-03-NumericalOnly','sample-05-TargetBounded')]
    else:
        receipt=[surface(run,out/'mass_surface.png')]
    save_json(out/'plot_sources.json',receipt)
