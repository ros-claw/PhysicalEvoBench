"""Contracts for prospective search and claims; no synthetic data is physical evidence."""

import copy
import json
import shutil
from pathlib import Path

import pytest

from physicalevobench.agents.search_worker import respond
from physicalevobench.evaluation.confirmation_audit import audit_episode
from physicalevobench.evaluation.confirmation_stats import exact_p, summarize
from physicalevobench.protocols.skill import SkillSpec

CHECKPOINT = 'b' * 64


def trial(gain, successes, version=0):
    return {"skill": SkillSpec(CHECKPOINT, version, gain).to_dict(), "feedback": [
        {"episode_id": f"trial-{version}-{i}", "success": i < successes,
         "failure_type": None if i < successes else "task_not_completed", "split": "train"}
        for i in range(8)]}


def request(agent, history):
    return {"agent": agent, "rng_seed": 1234, "history": history,
            "remaining_budget": (4 - len(history)) * 8}


def test_feedback_third_proposal_reacts_to_actual_training_outcomes():
    low = [trial(1., 2), trial(.9, 5, 1), trial(1.1, 1, 2)]
    high = [trial(1., 2), trial(.9, 1, 1), trial(1.1, 5, 2)]
    assert respond(request("feedback", low))["next_gain"] == .85
    assert respond(request("feedback", high))["next_gain"] == 1.15
    assert respond(request("random", low))["next_gain"] == respond(request("random", high))["next_gain"]
    low[1] = trial(.9, 2, 1)
    assert respond(request("feedback", low))["next_gain"] == .95


def test_train_selection_retains_original_on_ties_and_no_test_fields():
    history = [trial(1., 3), trial(.9, 3, 1), trial(1.1, 3, 2), trial(.95, 3, 3)]
    result = respond(request("feedback", history))
    assert result["selected_index"] == 0 and result["next_gain"] is None
    history[1]["feedback"][0]["object_mass_kg"] = 1.6
    with pytest.raises(TypeError):
        respond(request("feedback", history))
    bad = request("feedback", [trial(1., 2)])
    bad["remaining_budget"] = 7
    with pytest.raises(ValueError, match="budget"):
        respond(bad)


def test_exact_discordant_test_and_unchanged_skill_cannot_confirm():
    assert exact_p(0, 0) == 1
    assert exact_p(5, 0) == 1 / 32
    assert exact_p(0, 5) == 1
    assert exact_p(2, 2) == 11 / 16
    seed_rows, freezes = [], []
    for seed in range(3):
        seed_rows.append([{"condition_id": f"{seed}-{i}", "agent_id": arm,
                           "success": arm == "feedback", "joint_limit_violation_count": 0,
                           "unsafe_action_count": 0}
                          for i in range(24) for arm in ("frozen", "identity_replay", "feedback", "random")])
        freezes.append({arm: {"sha256": 'same'} for arm in ("frozen", "feedback")})
    result = summarize(seed_rows, freezes, samples=100)
    assert result["checks"]["all_holm_tests_pass"]
    assert result["claim"] == "NOT_CONFIRMED"
    assert not result["checks"]["retained_changed_at_least_two_seeds"]


def test_real_episode_audit_detects_tampered_actions_and_joint_counts(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'docs/evidence/experiments/reproduction-001'
    row = json.loads((source / 'test/baseline_episodes.jsonl').read_text().splitlines()[0])
    relative = Path(row['trace_artifact']).parent
    shutil.copytree(source / relative, tmp_path / relative)
    condition = json.loads((tmp_path / row['initial_state_artifact']).read_text())['condition']
    mapping = json.loads((source / 'action_mapping.json').read_text())['arm_action']
    audit_episode(tmp_path, row, condition, mapping)
    wrong = copy.deepcopy(row)
    wrong['joint_limit_violation_count'] += 1
    with pytest.raises(ValueError, match='Joint-limit counter'):
        audit_episode(tmp_path, wrong, condition, mapping)
    path = tmp_path / row['trace_artifact']
    trace = [json.loads(line) for line in path.read_text().splitlines()]
    trace[0]['applied_action'][0][0] += .1
    path.write_text(''.join(json.dumps(step) + '\n' for step in trace))
    with pytest.raises(ValueError, match='Executed action'):
        audit_episode(tmp_path, row, condition, mapping)
