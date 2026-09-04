from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from control_plane_reviewer.intake import intake
from control_plane_reviewer.review import ReviewError, canonical_patch


class IntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "worker@example.invalid")
        self.git("config", "user.name", "Worker")
        (self.source / "src").mkdir()
        (self.source / "tests").mkdir()
        (self.source / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.source / "tests" / "test_app.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.bundle = self.base / "base.bundle"
        self.git("bundle", "create", str(self.bundle), "HEAD")
        (self.source / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        self.patch = self.base / "submission.patch"
        self.patch.write_text(canonical_patch(self.source), encoding="utf-8", newline="")
        self.job = self.base / "job.json"
        self.job.write_text(json.dumps({"id": "d" * 32, "status": "completed", "diff": self.patch.read_text(encoding="utf-8")}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(("git", *args), cwd=self.source, text=True, capture_output=True, check=True).stdout

    def test_reconstructs_in_ide_sandbox_and_runs_ci(self) -> None:
        result = intake(self.job, self.bundle, self.patch, self.base / "sandboxes", ("src/**",))
        self.assertEqual("approve", result["verdict"])
        worktree = Path(result["workspace"])
        self.assertEqual(self.patch.read_text(encoding="utf-8"), canonical_patch(worktree))
        self.assertTrue(Path(result["review_artifact"]).is_file())
        head = subprocess.run(("git", "rev-list", "--count", "HEAD"), cwd=worktree, text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual("1", head)

    def test_tampered_patch_is_rejected_before_sandbox_creation(self) -> None:
        self.patch.write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(ReviewError):
            intake(self.job, self.bundle, self.patch, self.base / "sandboxes", ("src/**",))
        self.assertFalse((self.base / "sandboxes" / ("d" * 32)).exists())

    def test_existing_job_sandbox_is_not_overwritten(self) -> None:
        root = self.base / "sandboxes"
        destination = root / ("d" * 32)
        destination.mkdir(parents=True)
        marker = destination / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(ReviewError):
            intake(self.job, self.bundle, self.patch, root, ("src/**",))
        self.assertEqual("keep", marker.read_text(encoding="utf-8"))
