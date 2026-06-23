from __future__ import annotations

import yaml
from pathlib import Path
import enum
import os

class _LandlockUnavailableError(RuntimeError):
    pass

try:
    from py_landlock import Landlock, AccessFs
    _LANDLOCK_IMPORT_ERROR = None
except Exception as e:
    Landlock = None
    _LANDLOCK_IMPORT_ERROR = e

    class AccessFs(enum.IntFlag):
        EXECUTE = 1 << 0
        READ_FILE = 1 << 1
        READ_DIR = 1 << 2
        WRITE_FILE = 1 << 3
        TRUNCATE = 1 << 4
        MAKE_REG = 1 << 5
        MAKE_DIR = 1 << 6
        MAKE_SYM = 1 << 7
        REMOVE_FILE = 1 << 8
        REMOVE_DIR = 1 << 9
        MAKE_FIFO = 1 << 10
        MAKE_SOCK = 1 << 11


def _is_landlock_unavailable(exc):
    name = exc.__class__.__name__
    message = str(exc)
    return (
        name in ("LandlockNotAvailableError", "LandlockUnavailableError", "_LandlockUnavailableError")
        or "Landlock syscalls not available" in message
        or "No module named 'py_landlock'" in message
    )


def apply_security_policy(path):
    if path:
        policy = FileSystemPolicy()
        try:
            policy.load_file(path)
            policy.apply()
        except Exception as e:
            if policy.is_best_effort() and _is_landlock_unavailable(e):
                print(f"[policy.apply_security_policy]: Landlock unavailable, continuing without filesystem sandbox: {e}")
                return
            print(f"[policy.apply_security_policy]: Unexpected exception: {e}")
            raise
    else:
        print("[policy.apply_security_policy]: securityPolicyPath is not set")

class LandLockCompatibility(enum.Enum):
    BEST_EFFORT = 0
    HARD_REQUIREMENT = 1

class FileSystemPolicy:

    READ_ONLY_DIR_ACCESS = AccessFs.READ_DIR | AccessFs.READ_FILE
    READ_ONLY_FILE_ACCESS = AccessFs.READ_FILE
    READ_WRITE_DIR_ACCESS = (AccessFs.READ_FILE | AccessFs.READ_DIR
                             | AccessFs.WRITE_FILE | AccessFs.TRUNCATE
                             | AccessFs.MAKE_REG | AccessFs.MAKE_DIR
                             | AccessFs.MAKE_SYM | AccessFs.REMOVE_FILE
                             | AccessFs.REMOVE_DIR | AccessFs.MAKE_FIFO
                             | AccessFs.MAKE_SOCK)
    READ_WRITE_FILE_ACCESS = (AccessFs.READ_FILE | AccessFs.WRITE_FILE |
                              AccessFs.TRUNCATE)

    def __init__(self):
        self._compatibility = LandLockCompatibility.BEST_EFFORT
        self._read_only = []
        self._read_write = []

    def is_best_effort(self):
        return self._compatibility == LandLockCompatibility.BEST_EFFORT

    def load_file(self, path: str|Path):
        print(f"[FileSystemPolicy.load_file] loading policy from file {path}")
        policy = None
        with open(path, "r") as f:
            policy = yaml.safe_load(f)
        self.load_dict(policy)

    def load_str(self, policy: str):
        policy = yaml.safe_load(policy)
        self.load_dict(policy)

    def load_dict(self, policy: dict):
        version = policy.get('version')
        assert version == 1

        self._compatibility = LandLockCompatibility.BEST_EFFORT
        ll = policy.get('landlock')
        if ll:
            comp = ll.get('compatibility')
            if comp:
                self._compatibility = LandLockCompatibility[comp.upper()]

        fs = policy.get('filesystem_policy')

        ro = []
        rw = []
        if fs:
            ro = fs.get('read_only', [])
            if ro is None:
                ro = []
            rw = fs.get('read_write', [])
            if rw is None:
                ro = []
            if policy.get('include_workdir'):
                rw.append(os.getcwd())
        self._read_only = [Path(f'{p}') for p in ro]
        self._read_write = [Path(f'{p}') for p in rw]

    def apply(self):
        if Landlock is None:
            raise _LandlockUnavailableError(_LANDLOCK_IMPORT_ERROR)

        rod = list(filter(lambda p: p.is_dir(), self._read_only))
        rof = list(filter(lambda p: not p.is_dir(), self._read_only))
        rwd = list(filter(lambda p: p.is_dir(), self._read_write))
        rwf = list(filter(lambda p: not p.is_dir(), self._read_write))

        strict = self._compatibility == LandLockCompatibility.HARD_REQUIREMENT
        Landlock(strict=strict) \
            .allow_all_scope() \
            .allow_all_network() \
            .add_path_rule('/', access=AccessFs.EXECUTE) \
            .add_path_rule(*rwd, access=FileSystemPolicy.READ_WRITE_DIR_ACCESS) \
            .add_path_rule(*rwf, access=FileSystemPolicy.READ_WRITE_FILE_ACCESS) \
            .add_path_rule(*rod, access=FileSystemPolicy.READ_ONLY_DIR_ACCESS) \
            .add_path_rule(*rof, access=FileSystemPolicy.READ_ONLY_FILE_ACCESS) \
            .apply()

        print("[FileSystemPolicy.load_file] policy applied")
