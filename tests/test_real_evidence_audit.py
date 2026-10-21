"""Tamper checks use committed, genuinely recorded physics data; no simulator is required."""

import json
import shutil
from pathlib import Path

from physicalevobench.evaluation.audit import audit_run, read_jsonl


def test_real_evidence_rejects_changed_control_and_scores(tmp_path):
    source = Path(__file__).resolve().parents[1] / "docs/evidence/experiments/mvp-seed20261021-001"
    root = tmp_path / "copied-real-experiment"
    shutil.copytree(source, root)
    assert audit_run(root)["status"] == "PASS"
    episode = read_jsonl(root / "test/baseline_episodes.jsonl")[0]
    trace = root / episode["trace_artifact"]
    original = trace.read_text()
    rows = read_jsonl(trace)
    rows[0]["applied_action"][0][0] += 0.5
    trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
    assert any("Executed action disagrees" in issue for issue in audit_run(root)["issues"])
    trace.write_text(original)
    metrics_path = root / "report/metrics.json"
    metrics = json.loads(metrics_path.read_text())
    metrics["frozen"]["success_rate"] = 1.0
    metrics_path.write_text(json.dumps(metrics))
    assert any("Stored metrics disagree" in issue for issue in audit_run(root)["issues"])
