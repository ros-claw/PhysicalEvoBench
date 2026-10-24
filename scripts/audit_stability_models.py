"""Private CPU tensor/optimizer audit; never redistributes licensed checkpoint files."""

import argparse
import math
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.stability.audit import read


def main():
    import torch
    import yaml

    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    out = Path(p.parse_args().run_dir).absolute()
    reg = read(out/'registration.json')
    original = Path(reg['checkpoint_path'])
    if sha256(original) != reg['checkpoint_sha256']:
        raise ValueError('Original checkpoint changed')
    original_params = original.parent/'params/agent.yaml'
    if sha256(original_params) != 'ae5ccee81f45fda922d45cc5e72cc1a1734e8661054d244f137591b779ea59f6':
        raise ValueError('Original policy metadata differs from pinned NVIDIA configuration')
    expected_params = yaml.safe_load(original_params.read_text())
    expected_params['device'] = 'cuda:0'

    def nonfinite(value, path=''):
        bad = []
        if torch.is_tensor(value):
            if not torch.isfinite(value).all():
                bad.append(path)
        elif isinstance(value, dict):
            for key, item in value.items():
                bad.extend(nonfinite(item, path+'/'+str(key)))
        elif isinstance(value, (tuple, list)):
            for i, item in enumerate(value):
                bad.extend(nonfinite(item, path+'/'+str(i)))
        elif isinstance(value, float) and not math.isfinite(value):
            bad.append(path)
        return bad

    records = []
    configs = sorted(out.glob('s*-*/round-*/train/config.json'))
    if len(configs) != 18:
        raise ValueError('Require all 18 completed training jobs')
    for path in configs:
        cfg, freeze, previous_audit = read(path), read(path.parent/'freeze.json'), read(path.parent/'audit.json')
        before_path, after_path = Path(cfg['checkpoint_path']), Path(cfg['candidate_path'])
        if sha256(before_path) != cfg['checkpoint_sha256'] or sha256(after_path) != freeze['candidate_sha256']:
            raise ValueError('Checkpoint lineage/freeze digest changed')
        before = torch.load(before_path, map_location='cpu', weights_only=False)
        after = torch.load(after_path, map_location='cpu', weights_only=False)
        if nonfinite(before) or nonfinite(after):
            raise ValueError(f'Nonfinite parameter/optimizer state: {path.parent}')
        norms = {key: float((after['actor_state_dict'][key]-value).norm())
                 for key, value in before['actor_state_dict'].items() if value.is_floating_point()}
        if any(not math.isclose(value, previous_audit['actor_parameter_change_norms'][key],
                                rel_tol=1e-6, abs_tol=1e-8) for key, value in norms.items()):
            raise ValueError('Archived actor update norm disagrees with actual tensors')
        if not any(value > 0 for key, value in norms.items() if key.startswith('mlp.')):
            raise ValueError('Only distribution/optimizer changed, not the deterministic network')
        if yaml.safe_load((after_path.parent/'params/agent.yaml').read_text()) != expected_params:
            raise ValueError('Candidate policy metadata changed beyond the registered runtime override')
        records.append({'job': str(path.parent.relative_to(out)), 'input_sha256': sha256(before_path),
                        'candidate_sha256': sha256(after_path), 'deterministic_actor_changed': True,
                        'all_checkpoint_tensors_finite': True, 'optimizer_state_finite': True,
                        'metadata_preserved': True})
    result = {'status': 'PASS', 'models': records, 'jobs': len(records),
              'original_metadata_sha256': sha256(original_params), 'audit_source_sha256': sha256(Path(__file__)),
              'scope': 'actual actor/critic/optimizer tensors and YAML metadata; no performance-gain claim'}
    save_json(out/'private_model_audit.json', result)
    print(result['status'], result['jobs'], 'actual checkpoint pairs')


if __name__ == '__main__':
    main()
