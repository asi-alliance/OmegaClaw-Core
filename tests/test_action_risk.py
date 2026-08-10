import unittest

from src.action_risk import check


class ActionRiskTests(unittest.TestCase):
    def test_action_risk_classification(self):
        cases = [
            ("read-file", "public/readme.txt", "decision=allow, risk=low, reason=read-only"),
            ("websearch", "read public password policy", "decision=allow, risk=low, reason=read-only"),
            ("  READ-FILE  ", "  PUBLIC PASSWORD POLICY  ", "decision=allow, risk=low, reason=read-only"),
            ("write-file", "notes.txt", "decision=review, risk=medium, reason=state-changing"),
            ("unknown-skill", "ordinary argument", "decision=review, risk=medium, reason=unknown-action"),
            ("read-file", "/project/.env", "decision=review, risk=high, reason=sensitive-target"),
            ("read-file", "~/.ssh/id_ed25519", "decision=review, risk=high, reason=sensitive-target"),
            ("read-file", "/home/user/credentials.json", "decision=review, risk=high, reason=sensitive-target"),
            ("shell", "rm -rf /var/lib/app", "decision=block, risk=critical, reason=destructive-action"),
            ("shell", "cd /srv && sudo rm -fr data", "decision=block, risk=critical, reason=destructive-action"),
            ("shell", "docker volume rm omegaclaw-memory", "decision=block, risk=critical, reason=destructive-action"),
            ("shell", "DROP TABLE users", "decision=block, risk=critical, reason=destructive-action"),
            ("shell", "truncate database archive", "decision=block, risk=critical, reason=destructive-action"),
            ("shell", "git push origin main --force", "decision=block, risk=critical, reason=destructive-action"),
            ("shell", "git push -f origin main", "decision=block, risk=critical, reason=destructive-action"),
        ]
        for skill, target, expected in cases:
            with self.subTest(skill=skill, target=target):
                self.assertEqual(check(skill, target), expected)

    def test_destructive_precedes_sensitive_and_state_changing(self):
        self.assertEqual(
            check("write-file", "rm -rf /project/.env"),
            "decision=block, risk=critical, reason=destructive-action",
        )

    def test_sensitive_precedes_state_changing_and_read_only(self):
        expected = "decision=review, risk=high, reason=sensitive-target"
        self.assertEqual(check("write-file", "/project/.env"), expected)
        self.assertEqual(check("read-file", "/project/.env"), expected)

    def test_result_never_echoes_target(self):
        marker = "DO-NOT-ECHO-THIS-VALUE"
        self.assertNotIn(marker, check("read-file", f"credentials.json {marker}"))


if __name__ == "__main__":
    unittest.main()
