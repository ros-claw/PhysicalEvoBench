import pytest

from physicalevobench.evaluation.metrics import paired_metrics


def fixture_rows(successes, skill):
    return [dict(condition_id=f"fixture-{i}", seed=i, split="heldout_test", success=outcome,
                 execution_status="OK", base_checkpoint_sha256="a" * 64, skill_sha256=skill,
                 synthetic_fixture=True) for i, outcome in enumerate(successes)]


def test_paired_arithmetic_and_unmeasured_safety():
    frozen = fixture_rows([True, False, False, False], "b" * 64)
    updated = fixture_rows([True, True, True, False], "c" * 64)
    result = paired_metrics(frozen, list(reversed(updated)), allow_synthetic_fixture=True)
    assert result["frozen"]["successes"] == 1
    assert result["updated"]["success_rate"] == 0.75
    assert result["evolution_gain_percentage_points"] == 50
    assert result["synthetic_fixture"] is True
    assert result["unsafe_action_count"]["frozen"] == "not_measured"
    assert result["collision_count"] == "not_measured"


def test_synthetic_results_rejected_by_default():
    rows = fixture_rows([False], "b" * 64)
    with pytest.raises(ValueError, match="Synthetic"):
        paired_metrics(rows, rows)


def test_identical_skills_cannot_be_claimed_as_evolution():
    frozen = fixture_rows([False, False], "b" * 64)
    repeated = fixture_rows([True, False], "b" * 64)
    result = paired_metrics(frozen, repeated, allow_synthetic_fixture=True)
    assert result["evolution_gain_percentage_points"] == 50
    assert result["retained_skill_changed"] is False
    assert "replay variability" in result["interpretation"]


@pytest.mark.parametrize("change", [
    {"execution_status": "INFRA_FAILURE"}, {"seed": 999}, {"condition_id": "mismatch"},
    {"base_checkpoint_sha256": "d" * 64}, {"success": None},
])
def test_unfair_or_incomplete_pairs_rejected(change):
    rows = fixture_rows([True], "b" * 64)
    with pytest.raises(ValueError):
        paired_metrics(rows, [dict(rows[0], **change)], allow_synthetic_fixture=True)


def test_frozen_snapshot_and_duplicate_checks():
    rows = fixture_rows([False, True], "b" * 64)
    with pytest.raises(ValueError, match="Duplicate"):
        paired_metrics(rows + [rows[0]], rows, allow_synthetic_fixture=True)
    changed = [rows[0], dict(rows[1], skill_sha256="c" * 64)]
    with pytest.raises(ValueError, match="Skill changed"):
        paired_metrics(rows, changed, allow_synthetic_fixture=True)
