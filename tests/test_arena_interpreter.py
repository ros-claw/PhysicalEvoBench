import subprocess
import venv

from physicalevobench.adapters.arena_worker import arena_python_path


def test_launch_preserves_virtual_environment(tmp_path):
    arena = tmp_path / "arena"
    environment = arena / ".venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    python = arena_python_path({}, arena)
    assert python.is_symlink()
    result = subprocess.run([str(python), "-c", "import sys; print(sys.prefix)"],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == str(environment)
