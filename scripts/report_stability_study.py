"""Render a source-backed research result without changing registered criteria."""

import argparse
import math
from pathlib import Path

from physicalevobench.stability.audit import read, rows


def arm_rows(out, seed, arm):
    return [row for path in sorted((out/f'heldout-s{seed}').glob(f'block-*-{arm}/episodes.jsonl'))
            for row in rows(path)]


def exact_tail(wins, losses):
    n = wins+losses
    return sum(math.comb(n, k) for k in range(wins, n+1))/(2**n) if n else 1.


def render(out):
    result, reg, audit = read(out/'results.json'), read(out/'registration.json'), read(out/'delivery_audit.json')
    frozen = read(out/'all_trajectories_frozen.json')
    diagnostics = read(out/'supplemental_diagnostics.json')
    supported = result['status'] == 'STABLE_BOUNDED_TASK_ADAPTATION_SUPPORTED'
    text = [
        '# Three-seed, three-round stable adaptation confirmation', '',
        f"**{'Bounded official-task adaptation passed the registered primary checks.' if supported else 'Stable self-evolution was not established.'}**",
        'This is a completed fixed-budget physical experiment; CPU fixtures and diagnostics are not scored as learned improvement.', '',
        '[Preregistered protocol](STABILITY_PROTOCOL_V3_20261024.md). '
        '[Complete archive manifest](../evidence/stability-20261024/manifest.json).', '',
        f"Source: `{reg['source_commit']}`. All final heldout policies were frozen at `{frozen['frozen_at']}` before heldout launches.", '',
        '## Independent heldout results', '',
        'Each learning seed uses 128 fresh paired mass/seed conditions, evaluated in separate policy processes. '
        'Cells are official upstream lift successes out of 128. Success termination and the official '
        'predicate are unchanged. All arms share a numerical action envelope of +/-1000 raw action units. '
        'This is not a physical safety guarantee. Sustained holding is NOT_MEASURED in these early-terminating episodes.', '',
        '| Learning seed | Frozen | Identity replay | Retained round 1 | Retained round 2 | Retained round 3 | Equal-budget restart |',
        '| --- | --- | --- | --- | --- | --- | --- |',
    ]
    for seed, counts in enumerate(result['counts']):
        text.append('| '+str(seed)+' | '+' | '.join(str(counts[a]['successes']) for a in
                    ('frozen', 'identity', 'round1', 'round2', 'round3', 'restart'))+' |')
    text += ['', 'Different outcomes from identical retained checkpoint hashes are replay variability, not learning. '
             'Raw candidate updates and private promotion decisions are reported separately.', '',
             '| Registered comparison | Official success difference (pp) | Adjusted interval (pp) | Alpha |',
             '| --- | --- | --- | --- |']
    for name, value in result['comparisons'].items():
        lo, hi = value['interval']
        text.append(f"| {name} | {100*value['difference']:+.2f} | [{100*lo:+.2f}, {100*hi:+.2f}] | {value['alpha']:.6f} |")
    text += ['', 'Intervals use 10,000 paired condition-bootstrap draws stratified by the three fixed learned '
             'trajectories. They do not establish a population-level guarantee over future learning seeds. '
             'The six frozen-control comparisons use Bonferroni alpha=0.05/6; consecutive non-regression '
             'uses alpha=0.05/2 and a -5 pp tolerance. Bootstrap coverage is approximate.', '',
             '## Registered scientific gates', '', '| Gate | Passed |', '| --- | --- |']
    text.extend(f"| {name} | {value} |" for name, value in result['gates'].items())
    text += ['', f"Superiority to this particular equal-budget restart control: **{result['equal_budget_advantage_supported']}**.", '',
             '## Training, private validation and actual retained changes', '',
             'Every round trained for 614,400 real transitions. Continual training always resumed the preceding '
             'raw candidate; restart training always loaded the original. The learner selected its next rate '
             'from training rewards only. Private validation never selected the next training checkpoint.', '',
             '| Seed | Lane | Round | Incumbent / candidate official successes (of 64) | Promoted | Candidate SHA256 |',
             '| --- | --- | --- | --- | --- | --- |']
    for trajectory in frozen['trajectories']:
        for r, decision in enumerate(trajectory['decisions'], 1):
            text.append(f"| {trajectory['seed']} | {trajectory['algorithm']} | {r} | "
                        f"{decision['incumbent'][0]} / {decision['candidate'][0]} | {decision['promote']} | `{decision['candidate_sha256']}` |")
    hashes = {reg['checkpoint_path']: reg['checkpoint_sha256']}
    for config in out.glob('s*-*/round-*/train/config.json'):
        cfg = read(config)
        hashes[cfg['candidate_path']] = read(config.parent/'freeze.json')['candidate_sha256']
    text += ['', 'Retained checkpoint SHA256 prefixes (full hashes are in the archive):', '',
             '| Seed | Continual round 1 | Continual round 2 | Continual round 3 | Restart final |',
             '| --- | --- | --- | --- | --- |']
    for seed in range(3):
        main_lane, control = frozen['trajectories'][seed*2:seed*2+2]
        text.append('| '+str(seed)+' | '+' | '.join('`'+hashes[path][:12]+'`' for path in
                    [*main_lane['snapshots'], control['retained']])+' |')
    text += ['', '## Sampled safety and replay diagnostics', '',
             'These are pre-step joint-limit samples, with a 0.001 coordinate-unit tolerance; finger units are '
             'metres and arm units radians. Collision/contact safety and between-sample excursions remain unmeasured. '
             'Engineering acceptance margins are not a general safety guarantee.', '',
             '| Seed | Arm | Joint violations / joint samples | Episodes with a violation | Worst finger depth (mm) |',
             '| --- | --- | --- | --- | --- |']
    exact = []
    for seed in range(3):
        for arm in ('frozen', 'identity', 'round1', 'round2', 'round3', 'restart'):
            data = arm_rows(out, seed, arm)
            count = sum(r['safety']['violation_joint_samples'] for r in data)
            exposure = sum(r['safety']['joint_samples'] for r in data)
            any_count = sum(r['safety']['any_violation'] for r in data)
            depth = max(j['maximum_depth'] for r in data for j in r['safety']['per_joint'] if j['unit'] == 'm')
            text.append(f'| {seed} | {arm} | {count} / {exposure} | {any_count}/128 | {depth*1000:.3f} |')
        base, new = arm_rows(out, seed, 'frozen'), arm_rows(out, seed, 'round3')
        wins = sum(b['success'] and not a['success'] for a, b in zip(base, new, strict=True))
        losses = sum(a['success'] and not b['success'] for a, b in zip(base, new, strict=True))
        exact.append((seed, wins, losses, exact_tail(wins, losses)))
    text += ['', 'Supplemental exact one-sided sign-test diagnostics for final vs frozen '
             '(not replacements for registered bootstrap gates):', '',
             '| Seed | Discordant wins | Discordant losses | Exact one-sided p |', '| --- | --- | --- | --- |']
    text.extend(f'| {seed} | {wins} | {losses} | {probability:.8f} |'
                for seed, wins, losses, probability in exact)
    text += ['', '## Process-block and identical-policy diagnostics', '',
             '[Defined before heldout launch](STABILITY_ANALYSIS_SUPPLEMENT_20261024.md). '
             'These do not alter the registered primary decision. Whole blocks of 32 paired conditions '
             'are resampled within each learned trajectory to examine within-process correlation.', '',
             '| Final comparison | Difference (pp) | Process-block interval (pp) | Paired blocks |',
             '| --- | --- | --- | --- |']
    for name, value in diagnostics['block_bootstrap'].items():
        lo, hi = value['interval']
        text.append(f"| {name} | {value['difference']*100:+.2f} | [{lo*100:+.2f}, {hi*100:+.2f}] | {value['clusters']} |")
    text += ['', f"Both supplemental process-block intervals exclude zero positively: **{diagnostics['block_intervals_both_positive']}**. "
             'A positive per-condition interval without process-block corroboration is not evidence '
             'robust to this different uncertainty assumption.', '',
             '| Seed | Identical-policy safety replay passes | Failed guard components |',
             '| --- | --- | --- |']
    for item in diagnostics['identity_safety']:
        failed = ', '.join(name for name, passed in item['guards'].items() if not passed) or 'none'
        text.append(f"| {item['seed']} | {item['pass']} | {failed} |")
    text += ['', 'Identical model hashes can still yield different physical traces and sampled safety '
             'extremes. A failed replay guard exposes measurement variability; no rejected candidate '
             'is retroactively promoted.', '',
             '| Seed | Block | Frozen | Identity | Round 1 | Round 2 | Round 3 | Restart |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for block in diagnostics['process_blocks']:
        text.append(f"| {block['seed']} | {block['block']} | "+' | '.join(str(block['successes'][arm])
                    for arm in ('frozen', 'identity', 'round1', 'round2', 'round3', 'restart'))+' |')
    text += ['', '## Cost, integrity and interpretation', '',
             f"Independent delivery audit: **{audit['status']}**, {audit['evaluation_episodes']:,} completed "
             f"evaluation episodes across {audit['workers']} native workers, "
             f"{audit['training_transitions']:,} training transitions, {audit['completed_training_episodes']:,} "
             f"completed training episodes and {audit['unfinished_training_steps']:,} unfinished-rollout steps. "
             'Training completions do not count as evaluation successes. Earlier attempts consumed another '
             '3,686,400 training transitions, four diagnostic episodes, 24 failed holding-calibration episodes '
             'and 24 official-calibration episodes. They are separately accounted, not successful replications.', '',
             '**Earlier failures remain negative:** the v1 third continual seed overflowed its value loss at '
             'updates 112/113; all six first-round jobs and 14,892 completed training episodes are archived. '
             'The original policy reached the nominal goal 12/12 but held it at low speed for 0.30 s in 0/12 '
             'full-horizon calibration episodes; open-gripper scored 0/12 on both. v2 confirmation was blocked. '
             'The v3 primary metric was explicitly preregistered as the original official task before new '
             'training, rather than treating failed physical holding as success. See '
             '[v1 numerical failure archive](../evidence/stability-v1-numerical-failure-20261024/manifest.json).', '',
             'The independent audit checks raw actions/states, upstream official completion records, the '
             'common numerical action envelope, sampled safety, physical mass readback, matching initial states/public observations/velocities, '
             'source/checkpoint lineage, reservations, optimizer audits and final statistics. No model weights '
             'are redistributed. Source archives, hashed transition chunks, process logs, failure records and '
             'all episode traces are retained.', '',
             'A negative outcome distinguishes what failed in this fixed study: private promotion, '
             'heldout transfer, repeated-round gain, reproducibility or sampled safety. It does not prove '
             'the task unsolvable or all agents incapable. Even a positive result would support only '
             'bounded autonomous policy adaptation in this simulator, mass interval and five-second horizon; '
             'it would not prove unlimited or general self-evolution.', '',
             'Recompute from unpacked evidence: `uv run python scripts/audit_stability_study.py --run-dir <study>`. '
             'Private per-job tensor and transition audit: Arena interpreter, '
             '`-m physicalevobench.calibration.training_audit --run-dir <train>`, requiring the separately licensed checkpoints.', '']
    return '\n'.join(text)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    Path(a.output).write_text(render(Path(a.run_dir)))
