"""Export an immutable runtime package from a registered Git commit."""

import subprocess
from pathlib import Path

from physicalevobench.doctor import sha256


def snapshot_source(root, ref):
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
