"""Export an immutable runtime package from a registered Git commit."""

import fcntl
import subprocess
from contextlib import contextmanager
from pathlib import Path

from physicalevobench.doctor import sha256


@contextmanager
def source_lock(root,ref):
    directory=Path(root)/'.cache/study-source-locks'
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/(ref+'.lock')).open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream,fcntl.LOCK_UN)


def snapshot_source(root, ref):
    if len(ref)!=40 or any(c not in '0123456789abcdef' for c in ref):
        raise ValueError('Runtime source needs a full commit digest')
    with source_lock(root,ref):
        return _snapshot_source(root,ref)


def _snapshot_source(root, ref):
    root=Path(root)
    if len(ref)!=40 or any(c not in '0123456789abcdef' for c in ref):
        raise ValueError('Runtime source needs a full commit digest')
    target_root=root/'.cache/study-source'/ref
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',ref,'physicalevobench'],cwd=root,text=True).splitlines()
    expected={name for name in names if name.endswith('.py')}
    if not expected:
        raise ValueError('No runtime package in registered commit')
    for name in sorted(expected):
        target=target_root/name
        content=subprocess.check_output(['git','show',f'{ref}:{name}'],cwd=root)
        if target.exists():
            if target.read_bytes()!=content:
                raise ValueError('Immutable runtime source cache changed')
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content)
    actual={str(f.relative_to(target_root)) for f in (target_root/'physicalevobench').rglob('*.py')}
    if actual!=expected:
        raise ValueError('Unexpected module in frozen runtime package')
    return target_root,{name:sha256(target_root/name) for name in sorted(expected)}
