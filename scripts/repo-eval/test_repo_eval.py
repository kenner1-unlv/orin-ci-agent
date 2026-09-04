from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cases import CASES, case_by_id
from run import aggregate, calibrate_case, paths_allowed, score_attempt


class ManifestTests(unittest.TestCase):
    def test_suite_has_required_matrix(self):
        self.assertEqual(len(CASES), 12)
        self.assertEqual(len({case.id for case in CASES}), 12)
        counts = {category: sum(c.category == category for c in CASES) for category in
                  ("localized", "diagnosis", "multi-file", "test", "new-file", "no-op")}
        self.assertEqual(counts, {"localized": 3, "diagnosis": 3, "multi-file": 2,
                                  "test": 2, "new-file": 1, "no-op": 1})

    def test_all_fixtures_calibrate(self):
        with tempfile.TemporaryDirectory() as temp:
            results = [calibrate_case(case, Path(temp)) for case in CASES]
        self.assertTrue(all(result["passed"] for result in results), results)


class ScoringTests(unittest.TestCase):
    def _inputs(self, case_id="clamp_bounds", paths=None):
        case = case_by_id(case_id)
        status = "" if not paths else " M " + paths[0] + "\n"
        diff = "" if not paths else "patch"
        checks = [{"name": name, "exit_code": 0} for name in case.approved_checks]
        post = {"id": "a" * 32, "status": "completed", "workspace": "w", "git_status": status,
                "diff": diff, "checks": checks, "tool_calls": []}
        return case, post, dict(post), {"git_status": status, "diff": diff,
                                       "changed_paths": paths or [], "diff_check_exit_code": 0}

    def test_resolved_requires_external_oracle(self):
        case, post, fetched, evidence = self._inputs(paths=["math_utils.py"])
        score = score_attempt(case, post, fetched, evidence, {"passed": False}, 1.0)
        self.assertFalse(score["resolved"])

    def test_changed_path_enforcement(self):
        self.assertTrue(paths_allowed(["math_utils.py"], ["math_utils.py"]))
        self.assertFalse(paths_allowed(["math_utils.py", "secrets.txt"], ["math_utils.py"]))
        case, post, fetched, evidence = self._inputs(paths=["secrets.txt"])
        self.assertFalse(score_attempt(case, post, fetched, evidence, {"passed": True}, 1.0)["scope_compliant"])

    def test_no_op_requires_empty_diff(self):
        case, post, fetched, evidence = self._inputs("already_correct", ["flags.py"])
        score = score_attempt(case, post, fetched, evidence, {"passed": True}, 1.0)
        self.assertFalse(score["no_op_compliant"])
        self.assertFalse(score["resolved"])

    def test_first_attempt_gate(self):
        attempts = [{"case_id": CASES[i].id, "score": {"resolved": i < 9, "safe": True, "scope_compliant": True,
                                "retrieval_ok": True, "evidence_consistent": True,
                                "elapsed_seconds": 10.0}} for i in range(12)]
        self.assertTrue(aggregate(attempts)["promotion_gate_passed"])
        attempts[0]["score"]["safe"] = False
        self.assertFalse(aggregate(attempts)["promotion_gate_passed"])

    def test_repeatability_gate_requires_two_successes_per_case(self):
        attempts = []
        for case in CASES:
            for attempt in range(3):
                attempts.append({"case_id": case.id, "score": {
                    "resolved": case.id != CASES[0].id or attempt == 0,
                    "safe": True, "scope_compliant": True, "retrieval_ok": True,
                    "evidence_consistent": True, "elapsed_seconds": 10.0,
                }})
        result = aggregate(attempts)
        self.assertFalse(result["per_case_stability_gate"])
        self.assertFalse(result["promotion_gate_passed"])


if __name__ == "__main__":
    unittest.main()
