"""CPU contracts and analytic fixtures; none are physical evidence."""

import concurrent.futures
import subprocess
import time
from pathlib import Path

import pytest


def test_concurrent_source_export_never_observes_half_written_module(tmp_path,monkeypatch):
    from physicalevobench.calibration.source_snapshot import snapshot_source

    package=tmp_path/'physicalevobench'
    package.mkdir()
    (package/'__init__.py').write_text('VALUE = 7\n'*100)
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()
    git('init','-q')
    git('add','.')
    git('-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','CPU fixture')
    ref=git('rev-parse','HEAD')
    write=Path.write_bytes
    def slow_write(path,data):
        if 'study-source' in str(path) and path.name=='__init__.py':
            with path.open('wb') as stream:
                stream.write(data[:1])
                stream.flush()
                time.sleep(.03)
                stream.write(data[1:])
            return len(data)
        return write(path,data)
    monkeypatch.setattr(Path,'write_bytes',slow_write)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        values=list(pool.map(lambda _:snapshot_source(tmp_path,ref),range(12)))
    assert all(v==values[0] for v in values)
    (values[0][0]/'physicalevobench/__init__.py').write_text('TAMPERED')
    with pytest.raises(ValueError,match='cache changed'):
        snapshot_source(tmp_path,ref)
