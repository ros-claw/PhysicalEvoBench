import gzip
import json
import shutil
from pathlib import Path

import pytest

from physicalevobench.v02.audit import episode_metrics, records


@pytest.fixture
def native(tmp_path):
    target = tmp_path/'episode'
    shutil.copytree(Path(__file__).parent/'fixtures/v02_native_smoke', target)
    return target


def test_actual_native_terminal_and_substep_coverage(native):
    metric = episode_metrics(native, native/'control_semantics.json')
    assert metric['physics_samples'] == 1000
    assert metric['control_steps'] == 250
    assert metric['terminal_pre_reset_captured']
    assert not metric['holding']['stable_success']


def test_cannot_replace_terminal_with_post_reset_state(native):
    path = native/'terminal_pre_reset.json'
    terminal = json.loads(path.read_text())
    terminal['joint_position'] = json.loads((native/'initial_capture.json').read_text())['joint_position']
    path.write_text(json.dumps(terminal))
    with pytest.raises(ValueError, match='Terminal state'):
        episode_metrics(native, native/'control_semantics.json')


def test_missing_interior_substep_is_not_full_physics_coverage(native):
    path = native/'physics.jsonl.gz'
    frames = records(path)
    del frames[101]
    with gzip.open(path, 'wt') as stream:
        stream.writelines(json.dumps(f)+'\n' for f in frames)
    with pytest.raises(ValueError, match='ordering'):
        episode_metrics(native, native/'control_semantics.json')


def test_cannot_claim_target_clamp_from_unbounded_applied_action(native):
    path = native/'controls.jsonl.gz'
    controls = records(path)
    controls[30]['applied_target'] = controls[30]['processed_target']
    with gzip.open(path, 'wt') as stream:
        stream.writelines(json.dumps(f)+'\n' for f in controls)
    with pytest.raises(ValueError, match='envelope'):
        episode_metrics(native, native/'control_semantics.json')
