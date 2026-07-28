from pathlib import Path
import pytest
import tempfile
import multiprocessing
import subprocess
import traceback
from policy import FileSystemPolicy, LandLockCompatibility

_TEST_POLICY_YAML = """
version: 1
filesystem_policy:
  include_workdir: true
  read_only:
  - /
  - {dir}/ro_dir
  - {dir}/ro_file
  read_write:
  - .pytest_cache
  - {dir}/rw_dir
  - {dir}/rw_file
  - {dir}/ro_dir/rw_dir
landlock:
  compatibility: hard_requirement
"""

@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory):
    """Fixture creates the test directory structure"""
    dir = tmp_path_factory.mktemp("dir")
    Path(f"{dir}/ro_dir").mkdir()
    Path(f"{dir}/ro_dir/rw_dir").mkdir()
    temp_file(f"{dir}/ro_dir/file", "Read only file")
    temp_file(f"{dir}/ro_file", "Read only file")
    Path(f"{dir}/rw_dir").mkdir()
    temp_file(f"{dir}/rw_dir/file", "Read-write file")
    temp_file(f"{dir}/rw_file", "Read-write file")
    return dir

def apply_policy_to_dir(dir):
    """Apply _TEST_POLICY_YAML file policy to the passed dir"""
    text = _TEST_POLICY_YAML.format(dir=dir)
    policy = FileSystemPolicy()
    policy.load_str(text)
    policy.apply()

def run_in_separate_process(func, args):
    """Run func(queue, *args) in a separate process

    It is expected that func puts tuple (Bool, str) into the queue to return
    the result. First element of the tuple means if the test was successful,
    second element of the tuple contains error message if first element is
    False. This is required to allow applying test policy in subprocess only
    without restricting the test harness by the policy.
    """
    q = multiprocessing.Queue()
    proc = multiprocessing.Process(target=exception_catcher, args=(q, func, args))
    proc.start()
    proc.join()
    (passed, message) = q.get()
    assert passed, message

def exception_catcher(q, func, args):
    """Trampoline used to catch any exceptions thrown by func(q, *args)
    call."""
    try:
        func(q, *args)
    except Exception as e:
        q.put((False, f"Unexpected exception: {e}"))
        traceback.print_exc()

def temp_file(path, text):
    with open(path, "w") as f:
        f.write(text)

def test_read_write_dir(temp_dir):
    run_in_separate_process(process_test_read_write_dir, (temp_dir,))

def process_test_read_write_dir(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        # new dir
        Path(f"{temp_dir}/rw_dir/new_dir").mkdir()
        with open(f"{temp_dir}/rw_dir/new_dir/new_file", "w") as f:
            f.write("Hello, world!")
        Path(f"{temp_dir}/rw_dir/new_dir/new_file").unlink()
        Path(f"{temp_dir}/rw_dir/new_dir").rmdir()

        # new file
        with open(f"{temp_dir}/rw_dir/new_file", "w") as f:
            f.write("Hello, world!")
        Path(f"{temp_dir}/rw_dir/new_file").unlink()

        # old file write
        with open(f"{temp_dir}/rw_dir/file", "w") as f:
            f.write("Hello, world!")

        # old file remove
        Path(f"{temp_dir}/rw_dir/file").unlink()
    except PermissionError:
        q.put((False, f"Cannot write to read-write directory"))
    q.put((True, None))

def test_read_only_dir(temp_dir):
    run_in_separate_process(process_test_read_only_dir, (temp_dir,))

def process_test_read_only_dir(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        Path(f"{temp_dir}/ro_dir/new_dir").mkdir()
        q.put((False, "Can create subdir in the read-only dir"))
    except PermissionError as e:
        pass
    try:
        with open(f"{temp_dir}/ro_dir/new_file", "w") as f:
            f.write("Hello, world!")
        q.put((False, "Can create file in the read-only dir"))
    except PermissionError as e:
        pass
    q.put((True, None))

def test_read_only_file(temp_dir):
    run_in_separate_process(process_test_read_only_file, (temp_dir,))

def process_test_read_only_file(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        with open(f"{temp_dir}/ro_file", "w") as f:
            f.write("Hello, world!")
        q.put((False, "Can write to read-only file"))
    except PermissionError as e:
        pass
    q.put((True, None))

def test_read_write_file(temp_dir):
    run_in_separate_process(process_test_read_write_file, (temp_dir,))

def process_test_read_write_file(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        with open(f"{temp_dir}/rw_file", "w") as f:
            f.write("Hello, world!")
    except PermissionError:
        q.put((False, f"Cannot write to read-write file"))
    q.put((True, None))

def test_read_device(temp_dir):
    run_in_separate_process(process_test_read_device, (temp_dir,))

def process_test_read_device(q, temp_dir):
    policy = FileSystemPolicy()
    policy.load_str("""
        version: 1
        filesystem_policy:
          include_workdir: false
          read_only:
          - /dev/urandom
    """)
    policy.apply()
    with open(f"/dev/urandom", "r") as f:
        pass
    q.put((True, None))

def test_read_write_dir_under_read_only_dir(temp_dir):
    run_in_separate_process(process_test_read_write_dir_under_read_only_dir, (temp_dir,))

def process_test_read_write_dir_under_read_only_dir(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        # new dir
        Path(f"{temp_dir}/ro_dir/rw_dir/new_dir").mkdir()
        with open(f"{temp_dir}/ro_dir/rw_dir/new_dir/new_file", "w") as f:
            f.write("Hello, world!")
        Path(f"{temp_dir}/ro_dir/rw_dir/new_dir/new_file").unlink()
        Path(f"{temp_dir}/ro_dir/rw_dir/new_dir").rmdir()

        # new file
        with open(f"{temp_dir}/ro_dir/rw_dir/new_file", "w") as f:
            f.write("Hello, world!")
        Path(f"{temp_dir}/ro_dir/rw_dir/new_file").unlink()

        # old file write
        with open(f"{temp_dir}/ro_dir/rw_dir/file", "w") as f:
            f.write("Hello, world!")

        # old file remove
        Path(f"{temp_dir}/ro_dir/rw_dir/file").unlink()
    except PermissionError:
        q.put((False, f"Cannot write to read-write directory"))
    q.put((True, None))

def test_execute_shell(temp_dir):
    run_in_separate_process(process_test_execute_shell, (temp_dir,))

def process_test_execute_shell(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    path = Path(f'{temp_dir}/rw_dir/shell_dir')
    assert not path.exists()
    result = subprocess.run(['mkdir', '-p', str(path)])
    assert path.exists()
    path.rmdir()
    q.put((True, None))

def test_load_landlock_compatibility_flag():
    policy = FileSystemPolicy()
    policy.load_str( """
        version: 1
        landlock:
          compatibility: best_effort
        """)
    assert policy._compatibility == LandLockCompatibility.BEST_EFFORT

    policy = FileSystemPolicy()
    policy.load_str( """
        version: 1
        landlock:
          compatibility: hard_requirement
        """)
    assert policy._compatibility == LandLockCompatibility.HARD_REQUIREMENT


