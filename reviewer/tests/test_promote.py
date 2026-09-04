from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from control_plane_reviewer.promote import promote
from control_plane_reviewer.review import ReviewError, review


class PromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "ci@example.invalid")
        self.git("config", "user.name", "CI Agent")
        (self.repo / "src").mkdir()
        (self.repo / "tests").mkdir()
        (self.repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.repo / "tests" / "test_app.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.parent = self.git("rev-parse", "HEAD").strip()
        (self.repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        from control_plane_reviewer.review import canonical_patch
        self.job = self.base / "job.json"
        self.job.write_text(json.dumps({"id": "b" * 32, "status": "completed", "diff": canonical_patch(self.repo)}), encoding="utf-8")
        self.review_path = self.base / "review.json"
        review(self.job, self.repo, ("src/**",), ("git_diff_check",), self.review_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(("git", *args), cwd=self.repo, text=True, capture_output=True, check=True).stdout

    def test_approved_patch_creates_exactly_one_local_commit(self) -> None:
        artifact = promote(self.review_path, self.repo, "Promote worker patch", self.base / "promotion.json")
        self.assertEqual("committed", artifact["outcome"])
        self.assertEqual(self.parent, artifact["parent_commit"])
        self.assertEqual(artifact["commit_id"], self.git("rev-parse", "HEAD").strip())
        self.assertEqual("", self.git("status", "--porcelain"))
        self.assertEqual("src/app.py", self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").strip())

    def test_unapproved_review_creates_no_commit(self) -> None:
        data = json.loads(self.review_path.read_text(encoding="utf-8"))
        data["verdict"] = "request_changes"
        self.review_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ReviewError):
            promote(self.review_path, self.repo, "No", self.base / "promotion.json")
        self.assertEqual(self.parent, self.git("rev-parse", "HEAD").strip())

    def test_stale_or_extra_path_creates_no_commit(self) -> None:
        (self.repo / "src" / "extra.py").write_text("EXTRA = 1\n", encoding="utf-8")
        with self.assertRaises(ReviewError):
            promote(self.review_path, self.repo, "No", self.base / "promotion.json")
        self.assertEqual(self.parent, self.git("rev-parse", "HEAD").strip())

    def test_dirty_index_creates_no_commit(self) -> None:
        self.git("add", "src/app.py")
        with self.assertRaises(ReviewError):
            promote(self.review_path, self.repo, "No", self.base / "promotion.json")
        self.assertEqual(self.parent, self.git("rev-parse", "HEAD").strip())

    def test_failed_ci_check_creates_no_commit(self) -> None:
        (self.repo / "tests" / "test_app.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail('bad')\n", encoding="utf-8")
        # Re-review the new patch so only the independent CI rerun causes rejection.
        from control_plane_reviewer.review import canonical_patch
        self.job.write_text(json.dumps({"id": "c" * 32, "status": "completed", "diff": canonical_patch(self.repo)}), encoding="utf-8")
        second = self.base / "review2.json"
        review(self.job, self.repo, ("src/**", "tests/**"), (), second)
        with self.assertRaises(ReviewError):
            promote(second, self.repo, "No", self.base / "promotion.json")
        self.assertEqual(self.parent, self.git("rev-parse", "HEAD").strip())
