import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PROFILE = _ROOT / "profile"
if str(_PROFILE) not in sys.path:
    sys.path.insert(0, str(_PROFILE))

import policy  # noqa: E402


def test_best_effort_landlock_unavailable_does_not_raise(tmp_path, monkeypatch):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        """
version: 1
filesystem_policy:
  read_only:
  - /
  read_write: []
landlock:
  compatibility: best_effort
""",
        encoding="utf-8",
    )

    class UnavailableLandlock:
        def __init__(self, strict=False):
            raise RuntimeError("Landlock syscalls not available")

    monkeypatch.setattr(policy, "Landlock", UnavailableLandlock)

    policy.apply_security_policy(str(policy_file))


def test_hard_requirement_landlock_unavailable_raises(tmp_path, monkeypatch):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        """
version: 1
filesystem_policy:
  read_only:
  - /
  read_write: []
landlock:
  compatibility: hard_requirement
""",
        encoding="utf-8",
    )

    class UnavailableLandlock:
        def __init__(self, strict=False):
            raise RuntimeError("Landlock syscalls not available")

    monkeypatch.setattr(policy, "Landlock", UnavailableLandlock)

    try:
        policy.apply_security_policy(str(policy_file))
    except RuntimeError as exc:
        assert "Landlock syscalls not available" in str(exc)
    else:
        raise AssertionError("hard_requirement policy should not ignore unavailable Landlock")
