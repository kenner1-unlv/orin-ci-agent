from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from control_plane_reviewer.handoff import prepare_handoff
from control_plane_reviewer.review import ReviewError


class HandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "ci@example.invalid")
        self.git("config", "user.name", "CI Agent")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-qm", "promoted")
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.promotion = self.base / "promotion.json"
        self.write_promotion()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ("git", *args), cwd=self.repo, text=True, capture_output=True, check=True
        ).stdout

    def write_promotion(self, **updates: object) -> None:
        value = {
            "schema_version": 1,
            "promotion_id": "a" * 32,
            "outcome": "committed",
            "worker_job_id": "b" * 32,
            "review_id": "c" * 32,
            "parent_commit": "d" * 40,
            "commit_id": self.commit,
            "checks": [{"id": "git_diff_check", "status": "passed"}],
        }
        value.update(updates)
        self.promotion.write_text(json.dumps(value), encoding="utf-8")

    def test_prepares_exact_promoted_commit_bundle(self) -> None:
        bundle = self.base / "handoff.bundle"
        artifact = prepare_handoff(self.promotion, self.repo, bundle)
        self.assertEqual("prepared", artifact["outcome"])
        self.assertEqual(self.commit, artifact["commit_id"])
        self.assertRegex(artifact["bundle_sha256"], r"^[0-9a-f]{64}$")
        clone = self.base / "clone"
        subprocess.run(("git", "clone", "--quiet", str(bundle), str(clone)), check=True)
        self.assertEqual(
            self.commit,
            subprocess.run(
                ("git", "rev-parse", "HEAD"), cwd=clone, text=True,
                capture_output=True, check=True,
            ).stdout.strip(),
        )

    def test_rejects_dirty_or_wrong_revision(self) -> None:
        (self.repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ReviewError, "must be clean"):
            prepare_handoff(self.promotion, self.repo, self.base / "dirty.bundle")
        self.git("restore", "app.py")
        self.write_promotion(commit_id="e" * 40)
        with self.assertRaisesRegex(ReviewError, "does not match"):
            prepare_handoff(self.promotion, self.repo, self.base / "wrong.bundle")

    def test_rejects_uncommitted_promotion_artifact(self) -> None:
        self.write_promotion(outcome="rejected")
        with self.assertRaisesRegex(ReviewError, "does not authorize"):
            prepare_handoff(self.promotion, self.repo, self.base / "bad.bundle")

    def test_refuses_to_overwrite_bundle(self) -> None:
        bundle = self.base / "existing.bundle"
        bundle.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ReviewError, "must be new"):
            prepare_handoff(self.promotion, self.repo, bundle)


if __name__ == "__main__":
    unittest.main()
