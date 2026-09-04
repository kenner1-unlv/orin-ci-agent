from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import control_plane_reviewer.review as review_module
from control_plane_reviewer.review import ReviewError, canonical_patch, review


class ReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Review Test")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "value.txt").write_text("before\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        (self.repo / "src" / "value.txt").write_text("after\n", encoding="utf-8")
        self.job = self.base / "job.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> None:
        subprocess.run(("git", *args), cwd=self.repo, text=True, capture_output=True, check=True)

    def write_job(self, patch: str | None = None) -> None:
        record = {"id": "a" * 32, "status": "completed", "diff": canonical_patch(self.repo)}
        if patch is not None:
            record["diff"] = patch
        self.job.write_text(json.dumps(record), encoding="utf-8")

    def run_review(self, *, allow=("src/**",), checks=(), name="review.json"):
        return review(self.job, self.repo, allow, checks, self.base / name)

    def test_matching_patch_is_approved_and_unchanged(self) -> None:
        self.write_job()
        before = canonical_patch(self.repo)
        artifact = self.run_review(checks=("git_diff_check",))
        self.assertEqual("approve", artifact["verdict"])
        self.assertEqual(before, canonical_patch(self.repo))
        self.assertEqual(artifact["state_before"], artifact["state_after"])

    def test_mismatch_requests_changes(self) -> None:
        self.write_job("different")
        artifact = self.run_review()
        self.assertEqual("request_changes", artifact["verdict"])
        self.assertIn("PATCH_MISMATCH", {item["code"] for item in artifact["findings"]})

    def test_out_of_scope_untracked_file_requests_changes(self) -> None:
        (self.repo / "notes.txt").write_text("unrelated\n", encoding="utf-8")
        self.write_job()
        artifact = self.run_review()
        self.assertIn("PATH_OUT_OF_SCOPE", {item["code"] for item in artifact["findings"]})

    def test_likely_credential_requests_changes(self) -> None:
        (self.repo / "src" / "value.txt").write_text("api_key = 'abcdefghijklmnop1234'\n", encoding="utf-8")
        self.write_job()
        artifact = self.run_review()
        self.assertIn("LIKELY_CREDENTIAL", {item["code"] for item in artifact["findings"]})

    def test_binary_change_requests_changes(self) -> None:
        (self.repo / "src" / "blob.bin").write_bytes(bytes(range(256)) * 4)
        self.write_job()
        artifact = self.run_review()
        self.assertIn("BINARY_CHANGE", {item["code"] for item in artifact["findings"]})

    def test_failed_check_requests_changes(self) -> None:
        self.write_job()
        artifact = self.run_review(checks=("python_unittest",))
        self.assertIn("CHECK_FAILED", {item["code"] for item in artifact["findings"]})

    def test_mutating_check_is_detected(self) -> None:
        self.write_job()
        review_module.CHECKS["test_mutation"] = (sys.executable, "-c", "open('ignored.tmp','w').write('x')")
        try:
            artifact = self.run_review(checks=("test_mutation",))
        finally:
            del review_module.CHECKS["test_mutation"]
        self.assertIn("REVIEW_MUTATED_WORKSPACE", {item["code"] for item in artifact["findings"]})

    def test_existing_output_and_duplicate_checks_are_invalid(self) -> None:
        self.write_job()
        output = self.base / "existing.json"
        output.write_text("keep", encoding="utf-8")
        with self.assertRaises(ReviewError):
            review(self.job, self.repo, ("src/**",), (), output)
        with self.assertRaises(ReviewError):
            review(self.job, self.repo, ("src/**",), ("git_diff_check", "git_diff_check"), self.base / "new.json")
        self.assertEqual("keep", output.read_text(encoding="utf-8"))

    def test_artifact_has_required_audit_fields(self) -> None:
        self.write_job()
        artifact = self.run_review()
        persisted = json.loads((self.base / "review.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact, persisted)
        required = {"schema_version", "review_id", "worker_job_id", "started_at", "finished_at",
                    "verdict", "patch_sha256", "changed_paths", "findings", "checks",
                    "state_before", "state_after"}
        self.assertEqual(set(), required - artifact.keys())

    def test_output_inside_workspace_is_invalid(self) -> None:
        self.write_job()
        with self.assertRaises(ReviewError):
            review(self.job, self.repo, ("src/**",), (), self.repo / "review.json")


if __name__ == "__main__":
    unittest.main()
