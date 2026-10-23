"""Coordinate-aware sampled safety diagnostics, independent of policy actions."""


def summarize_safety(positions, limits, names, dt, tolerance=0.001):
    if not positions or len(limits) != len(names) or dt <= 0:
        raise ValueError('Need nonempty samples, named limits and positive dt')
    result = []
    for j, name in enumerate(names):
        low, high = limits[j]
        depths = [max(low - q[j], q[j] - high, 0.0) for q in positions]
        count = sum(d > tolerance for d in depths)
        result.append({'joint': name, 'unit': 'm' if 'finger' in name else 'rad',
                       'samples_over_tolerance': count, 'duration_over_tolerance_s': count * dt,
                       'maximum_depth': max(depths),
                       'integrated_depth_coordinate_seconds': sum(depths) * dt})
    total = sum(r['samples_over_tolerance'] for r in result)
    return {'schema_version': 'sampled-safety-1', 'samples': len(positions), 'step_dt': dt,
            'tolerance_coordinate_units': tolerance, 'joint_samples': len(positions) * len(names),
            'violation_joint_samples': total, 'any_violation': total > 0,
            'violations_per_1000_joint_samples': 1000 * total / (len(positions) * len(names)),
            'per_joint': result, 'collision': 'NOT_MEASURED',
            'scope': 'pre-step samples; no between-sample or contact safety claim'}
