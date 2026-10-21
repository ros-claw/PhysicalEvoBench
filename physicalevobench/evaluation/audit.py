"""Independently inspect experiment artifacts; do not call the agent or simulator."""

import json
import math
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.metrics import paired_metrics
from physicalevobench.protocols.feedback import TrainingFeedback
from physicalevobench.protocols.skill import SkillSpec


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def near(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(near(x, y) for x, y in zip(a, b, strict=True))
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-6)


def audit_run(directory):
    root = Path(directory).absolute()
    issues = []
    try:
        config = json.loads((root / "config_resolved.json").read_text())
        hashes = json.loads((root / "manifest_hashes.json").read_text())
        manifests = {split: read_jsonl(root / "splits" / f"{split}.jsonl") for split in hashes}
        seen_ids, seen_seeds = set(), set()
        for split, rows in manifests.items():
            if sha256(root / "splits" / f"{split}.jsonl") != hashes[split]:
                issues.append(f"Manifest changed: {split}")
            for row in rows:
                if row["split"] != split or row["condition_id"] in seen_ids or row["seed"] in seen_seeds:
                    issues.append("Manifest split or seed overlap")
                seen_ids.add(row["condition_id"])
                seen_seeds.add(row["seed"])
        frozen = read_jsonl(root / "test/baseline_episodes.jsonl")
        updated = read_jsonl(root / "test/updated_episodes.jsonl")
        metrics = paired_metrics(frozen, updated, bootstrap_seed=config["seed"])
        stored_metrics = json.loads((root / "report/metrics.json").read_text())
        for key, value in metrics.items():
            if stored_metrics.get(key) != value:
                issues.append(f"Stored metrics disagree with independent calculation: {key}")
        expected = {row["condition_id"] for row in manifests["heldout_test"]}
        if len(expected) < 16 or expected != {row["condition_id"] for row in frozen}:
            issues.append("Incomplete heldout coverage")
        freeze = json.loads((root / "frozen_skills.json").read_text())
        baseline_skill = SkillSpec.from_dict(json.loads((root / "baseline/skill_v0.json").read_text()))
        updated_skill = SkillSpec.from_dict(json.loads((root / "evolution/final_skill.json").read_text()))
        if not freeze["updater_process_terminated"]:
            issues.append("Updater not frozen")
        for rows, skill, key in [(frozen, baseline_skill, "baseline_sha256"),
                                  (updated, updated_skill, "updated_sha256")]:
            if freeze[key] != skill.sha256 or any(row["skill_sha256"] != skill.sha256 for row in rows):
                issues.append("Frozen skill mismatch")
        training = read_jsonl(root / "evolution/training_episodes.jsonl")
        request = json.loads((root / "evolution/agent_request.json").read_text())
        for payload in request["training_feedback"]:
            TrainingFeedback.from_payload(payload)
        proposal = json.loads((root / "evolution/agent_response.json").read_text())["proposal"]
        if proposal is None or not any(not row["success"] for row in training):
            issues.append("No failure-linked physical candidate")
        ledger = json.loads((root / "budget_ledger.json").read_text())
        for split, limit in config["budgets"].items():
            used = [row for row in ledger if row["split"] == split]
            if len(used) > limit or [row["used"] for row in used] != list(range(1, len(used) + 1)):
                issues.append(f"Budget ledger invalid: {split}")
        validation = read_jsonl(root / "evolution/incumbent_validation_episodes.jsonl")
        validation += read_jsonl(root / "evolution/candidate_validation_episodes.jsonl")
        all_rows = training + validation + frozen + updated
        registry = {row["condition_id"]: row for rows in manifests.values() for row in rows}
        if len(ledger) != len(all_rows) or {x["episode_id"] for x in ledger} != {x["episode_id"] for x in all_rows}:
            issues.append("Ledger and episode evidence disagree")
        for row in all_rows:
            if row.get("synthetic_fixture") or row["execution_status"] != "OK":
                issues.append("Nonphysical or failed infrastructure included in score")
            for field in ("trace_artifact", "initial_state_artifact", "upstream_artifact"):
                path = (root / row[field]).resolve()
                if not path.is_relative_to(root.resolve()) or not path.is_file():
                    raise ValueError("Missing or escaping evidence path")
            trace = read_jsonl(root / row["trace_artifact"])
            if len(trace) != row["steps"]:
                issues.append(f"Trace length mismatch: {row['episode_id']}")
            official = [x for x in read_jsonl(root / row["upstream_artifact"]) if x["episode_length"] > 0]
            if len(official) != 1 or official[0]["success"] != row["success"]:
                issues.append("Upstream score mismatch")
            state = json.loads((root / row["initial_state_artifact"]).read_text())
            if state["condition"] != registry[row["condition_id"]] or row["seed"] != registry[row["condition_id"]]["seed"]:
                issues.append("Executed condition differs from frozen manifest")
            if not near(state["mass_readback_kg"][0][0], state["condition"]["object_mass_kg"]):
                issues.append("Physical mass mismatch")
        for old, new in zip(sorted(frozen, key=lambda x: x["condition_id"]),
                            sorted(updated, key=lambda x: x["condition_id"]), strict=True):
            a = json.loads((root / old["initial_state_artifact"]).read_text())
            b = json.loads((root / new["initial_state_artifact"]).read_text())
            for field in ["mass_readback_kg", "inertia_readback", "joint_position", "object_position", "target_command"]:
                if not near(a[field], b[field]):
                    issues.append(f"Paired initial state differs: {old['condition_id']}:{field}")
        result = {"status": "PASS" if not issues else "INCOMPLETE", "issues": issues,
                  "checked_physical_episodes": len(all_rows), "checked_test_pairs": metrics["num_pairs"],
                  "collision_count": "not_measured", "video_complete": any(root.rglob("*.mp4")),
                  "scope": "Local evidence consistency; not malicious-code isolation or physical MVP acceptance"}
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {"status": "INCOMPLETE", "issues": [*issues, str(error)]}
    save_json(root / "audit.json", result)
    return result
