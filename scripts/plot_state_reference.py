"""Standalone physical traces and finite calibration counts, no simulations."""

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read, rows
from physicalevobench.v02.audit import audit_run, records


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--v1',required=True)
    p.add_argument('--v2',required=True)
    p.add_argument('--v2-development',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    v1,v2,development,out=map(Path,(a.v1,a.v2,a.v2_development,a.output))
    for run in (v1,v2,development):
        audit_run(run)
    out.mkdir(parents=True,exist_ok=True)
    first=next(r for r in rows(v1/'StateBasedReference/episodes.jsonl') if not r['success'])
    second=rows(development/'StateBasedReference/episodes.jsonl')[0]
    cases=[(v1/'StateBasedReference',first,'V1: first failed heavy-load condition'),
           (development/'StateBasedReference',second,'V2: first heavy-load development condition')]
    fig,axes=plt.subplots(4,2,figsize=(13,11),sharex=True,sharey='row',layout='constrained')
    phases=['approach','descend','close','probe','lift','hold','recover','failed']
    receipts=[]
    for col,(worker,row,label) in enumerate(cases):
        ep=worker/'episodes'/row['episode_id']
        frames=records(ep/'physics.jsonl.gz')
        trace=records(ep/'trace.jsonl.gz')
        initial=read(ep/'initial_capture.json')
        meta=read(worker/'control_semantics.json')
        times=[(f['physics_step_global']-initial['physics_step_global'])*meta['physics_dt'] for f in frames]
        axes[0,col].plot(times,[100*math.dist(f['object_position'][0],f['goal_position_world'][0]) for f in frames],color='#235789')
        axes[0,col].axhline(5,color='#565b61',ls=':',lw=1)
        axes[1,col].plot(times,[math.sqrt(sum(v*v for v in f['object_velocity'][0][:3])) for f in frames],color='#235789')
        axes[1,col].axhline(.2,color='#565b61',ls=':',lw=1)
        control_times=[s['step']*meta['control_dt'] for s in trace]
        axes[2,col].plot(control_times,[max(abs(v) for v in s['policy_diagnostics'].get('bounded_joint_integral_rad',[0]*7)) for s in trace],color='#a66d00')
        axes[2,col].axhline(.12,color='#565b61',ls=':',lw=1)
        axes[3,col].step(control_times,[phases.index(s['policy_diagnostics']['phase']) for s in trace],where='post',color='#235789')
        condition=read(ep/'initial_state.json')['condition']
        axes[0,col].set_title(f'{label}\nseed {condition["seed"]}; mass {condition["object_mass_kg"]:g} kg',fontsize=11)
        axes[3,col].set_xlabel('Elapsed physical time (s)')
        for ax in axes[:,col]:
            ax.spines[['top','right']].set_visible(False)
            ax.grid(axis='y',alpha=.15)
            ax.set_xlim(0,10)
        for ax in axes[:3,col]:
            ax.set_ylim(bottom=0)
        receipts.append({'episode':str(ep),'episode_sha256':sha256(ep/'episode.json'),
                         'physics_sha256':sha256(ep/'physics.jsonl.gz'),'trace_sha256':sha256(ep/'trace.jsonl.gz')})
    axes[0,0].set_ylabel('Object-to-goal distance (cm)\nDotted: 5 cm tolerance')
    axes[1,0].set_ylabel('Object speed (m/s)\nDotted: 0.2 m/s hold limit')
    axes[2,0].set_ylabel('Max |joint integral bias| (rad)\nDotted: 0.12 rad bound')
    axes[3,0].set_ylabel('Observed teacher phase')
    axes[3,0].set_yticks(range(len(phases)),phases)
    fig.suptitle('Recorded reference-controller trajectories, common ten-second task\nDifferent diagnostic conditions, each n=1; illustration, not paired efficacy inference',fontsize=13)
    fig.savefig(out/'loaded_trajectory.png',dpi=150)
    plt.close(fig)
    summaries=[read(run/'reference_diagnosis.json')['surface'] for run in (v1,v2)]
    matrix=[[s[f'{controller}-{m:g}kg']['holding'] for m in (.1,.4)] for s in summaries
            for controller in ('StateBasedReference','StateBasedReferenceOpen')]
    fig,ax=plt.subplots(figsize=(7,5),layout='constrained')
    image=ax.imshow(matrix,vmin=0,vmax=6,cmap='Blues',aspect='auto')
    for i,row in enumerate(matrix):
        for j,value in enumerate(row):
            ax.text(j,i,f'{value}/6',ha='center',va='center',fontsize=14,color='white' if value>3 else '#202328')
    ax.set_xticks([0,1],['0.1 kg','0.4 kg'])
    ax.set_yticks(range(4),['V1 reference','V1 open-gripper','V2 reference','V2 open-gripper'])
    ax.set_title('Effective holds on independently registered conditions\nSix conditions per cell; finite calibration counts',fontsize=12)
    fig.colorbar(image,ax=ax,label='Completed effective holds',ticks=range(7))
    fig.savefig(out/'independent_counts.png',dpi=150)
    plt.close(fig)
    save_json(out/'plot_sources.json',{'cases':receipts,'registrations':{str(run):sha256(run/'registration.json') for run in (v1,v2,development)},
              'scope':'Standalone observed traces/counts; lines connect recorded samples, no between-sample or learner-population claim'})


if __name__=='__main__':
    main()
