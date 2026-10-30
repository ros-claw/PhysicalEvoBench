"""Portable qualification identity: content hashes, independent of old run paths."""

from physicalevobench.doctor import sha256

EXECUTION_FILES = (
    'physicalevobench/core/collect.py', 'physicalevobench/core/native.py',
    'physicalevobench/core/program.py', 'physicalevobench/core/expressions.py',
    'physicalevobench/core/metrics.py', 'physicalevobench/v02/reference_native.py',
    'physicalevobench/v02/reference.py', 'physicalevobench/v02/native.py',
    'physicalevobench/v02/execution.py', 'physicalevobench/v02/audit.py',
    'physicalevobench/adapters/lift_worker.py', 'physicalevobench/adapters/arena_worker.py',
    'physicalevobench/calibration/policies.py', 'physicalevobench/stability/audit.py',
    'physicalevobench/stability/metrics.py', 'physicalevobench/protocols/skill.py',
)


def validate_execution(root, receipt, base):
    from physicalevobench.development.place import starter_program
    from physicalevobench.v02.reference_artifact import digest
    expected = receipt.get('execution_files', {})
    if set(expected) != set(EXECUTION_FILES):
        raise ValueError('Qualification needs portable execution file hashes')
    for name, value in expected.items():
        if sha256(root/name) != value:
            raise ValueError('Execution semantics changed after qualification: '+name)
    if receipt.get('initial_reference_sha256') != digest(base):
        raise ValueError('Common initial ability differs from qualified configuration')
    if receipt.get('starter_hash') != starter_program().sha256:
        raise ValueError('Common initial executable differs from qualified configuration')
