"""Generate a standalone HTML readout only from audited, real experiment artifacts."""

import html
import json
from pathlib import Path

from physicalevobench.evaluation.audit import audit_run, read_jsonl


def generate_report(directory):
    root = Path(directory).absolute()
    audit = audit_run(root)
    if audit["status"] != "PASS":
        raise ValueError(f"Incomplete experiment evidence: {audit['issues']}")
    metrics = json.loads((root / "report/metrics.json").read_text())
    decision = metrics["decision"]
    groups = [("Frozen", metrics["frozen"]), ("Updated (after gate)", metrics["updated"])]
    table = "".join(f"<tr><td>{name}</td><td>{group['successes']} / {group['episodes']}</td>"
                    f"<td>{group['success_rate']:.1%}</td></tr>" for name, group in groups)
    episodes = []
    for path in ["evolution/training_episodes.jsonl", "evolution/incumbent_validation_episodes.jsonl",
                 "evolution/candidate_validation_episodes.jsonl", "test/baseline_episodes.jsonl",
                 "test/updated_episodes.jsonl"]:
        episodes.extend(read_jsonl(root / path))
    links = "".join(f"<tr><td>{html.escape(row['episode_id'])}</td><td>{row['split']}</td>"
                    f"<td>{row['success']}</td><td>{row['steps']}</td><td>"
                    f"<a href='../{html.escape(row['trace_artifact'], quote=True)}'>action trace</a> · "
                    f"<a href='../{html.escape(row['initial_state_artifact'], quote=True)}'>initial state</a>"
                    "</td></tr>" for row in episodes)
    interval = metrics["paired_bootstrap_95_percent_interval_pp"]
    videos = "".join(f'<p><video controls width="840" src="../videos/{html.escape(path.name, quote=True)}"></video></p>'
                     for path in (root / "videos").glob("*.mp4"))
    text = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PhysicalEvoBench {html.escape(root.name)}</title>
<style>body{{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#192735}}
table{{border-collapse:collapse;width:100%;margin:20px 0}}td,th{{text-align:left;padding:8px;border-bottom:1px solid #ccd4dd}}
pre{{white-space:pre-wrap;background:#eef2f6;padding:16px}}a{{color:#165fa5}}</style>
<h1>PhysicalEvoBench · {html.escape(root.name)}</h1>
<p>Real PhysX Franka Lift · state-observation skill-adaptation track · local evidence audit: PASS.</p>
<p>This single-run comparison does not establish general self-improvement or algorithmic superiority.</p>
<p><strong>{html.escape(metrics['interpretation'])}</strong></p>
<table><tr><th>Group</th><th>Successes / episodes</th><th>Success rate</th></tr>{table}</table>
<p>Observed paired success-rate difference (nominal Evolution Gain formula):
<strong>{metrics['evolution_gain_percentage_points']:+.2f} percentage points</strong>.
Paired condition bootstrap 95% interval: [{interval[0]:+.2f}, {interval[1]:+.2f}] pp.
This interval excludes between-run seed uncertainty.</p>
<p>Validation decision: <strong>{html.escape(decision['decision'])}</strong>.
A rolled-back candidate is not a retained improvement.</p>
<p>Training episodes: {metrics['training_episode_budget_used']}; validation episodes:
{metrics['validation_episode_budget_used']}; heldout episodes: {metrics['test_episode_budget_used']}.
Model token use: 0. Collision count: <strong>not_measured</strong>. Joint-limit counts are sampled
pre-step positions against hard limits, with a 0.001 coordinate-unit tolerance; inspect each episode.</p>
<p>Test joint-limit samples: Frozen <strong>{metrics['joint_limit_violation_count']['frozen']}</strong>;
final agent <strong>{metrics['joint_limit_violation_count']['updated']}</strong>.
Passing a validation gate does not establish safety on new conditions.</p>
<p>Public heldout manifests are not a secret test service. Budget-matched random search is not implemented.</p>
<h2>Physical video</h2><p>Separate real-camera replays, excluded from scored episodes.
Refer to their source experiment's validation decision. A video is not an improvement claim.</p>{videos or '<p>not_recorded</p>'}
<p><a href="metrics.json">Metrics JSON</a> · <a href="../audit.json">Audit</a> ·
<a href="../provenance.json">Provenance</a> · <a href="../evolution/skill_diff.json">Skill diff</a> ·
<a href="../evolution/agent_request.json">Updater's exact train-only input</a></p>
<h2>Auditable physical episodes</h2><table><tr><th>Episode</th><th>Split</th><th>Success</th><th>Steps</th><th>Evidence</th></tr>{links}</table>
<h2>Validation gate</h2><pre>{html.escape(json.dumps(decision, indent=2))}</pre></html>"""
    path = root / "report/index.html"
    path.write_text(text)
    return path
