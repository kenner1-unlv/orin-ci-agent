"""Deterministic evaluator-owned fixtures for the bounded editor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Oracle:
    source: str
    timeout_seconds: int = 20


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    instruction: str
    approved_checks: tuple[str, ...]
    allowed_changed_paths: tuple[str, ...]
    files: Mapping[str, str]
    reference_files: Mapping[str, str | None]
    oracle: Oracle


def _oracle(body: str) -> Oracle:
    return Oracle("""import pathlib, sys\nroot = pathlib.Path(sys.argv[1]).resolve()\nsys.path.insert(0, str(root))\n""" + body)


CASES: tuple[Case, ...] = (
    Case("clamp_bounds", "localized", "Fix clamp so values above the upper bound are capped.",
         ("python_unittest", "git_diff_check"), ("math_utils.py", "tests/*.py", "test_*.py"),
         {"math_utils.py": "def clamp(value, low, high):\n    return max(low, value)\n", "tests/test_smoke.py": "import unittest\nclass Smoke(unittest.TestCase):\n    def test_true(self): self.assertTrue(True)\n"},
         {"math_utils.py": "def clamp(value, low, high):\n    return min(high, max(low, value))\n"},
         _oracle("from math_utils import clamp\nassert clamp(12, 0, 10) == 10\nassert clamp(-2, 0, 10) == 0\n")),
    Case("slug_whitespace", "localized", "Make slugify collapse surrounding and repeated whitespace into single hyphens.",
         ("python_compileall", "git_diff_check"), ("text.py", "tests/*.py", "test_*.py"),
         {"text.py": "def slugify(value):\n    return value.lower().replace(' ', '-')\n"},
         {"text.py": "def slugify(value):\n    return '-'.join(value.lower().split())\n"},
         _oracle("from text import slugify\nassert slugify('  Hello   World ') == 'hello-world'\n")),
    Case("mean_empty", "localized", "Make mean return 0.0 for an empty input without changing non-empty behavior.",
         ("python_compileall", "git_diff_check"), ("stats.py", "tests/*.py", "test_*.py"),
         {"stats.py": "def mean(values):\n    return sum(values) / len(values)\n"},
         {"stats.py": "def mean(values):\n    return sum(values) / len(values) if values else 0.0\n"},
         _oracle("from stats import mean\nassert mean([]) == 0.0\nassert mean([2, 4]) == 3\n")),
    Case("config_alias", "diagnosis", "The application ignores the documented 'colour' setting. Diagnose and fix the lookup while preserving 'color'.",
         ("python_compileall", "git_diff_check"), ("config.py", "tests/*.py", "test_*.py"),
         {"config.py": "def theme(config):\n    return config.get('color', 'blue')\n", "README.md": "Theme accepts `color` or its documented alias `colour`.\n"},
         {"config.py": "def theme(config):\n    return config.get('color', config.get('colour', 'blue'))\n"},
         _oracle("from config import theme\nassert theme({'colour': 'red'}) == 'red'\nassert theme({'color': 'green', 'colour': 'red'}) == 'green'\n")),
    Case("csv_header", "diagnosis", "Rows are being treated as headers. Find and repair the CSV parsing defect.",
         ("python_compileall", "git_diff_check"), ("reader.py", "tests/*.py", "test_*.py"),
         {"reader.py": "import csv\ndef records(stream):\n    return list(csv.DictReader(stream, fieldnames=['name', 'age']))\n", "format.md": "CSV input includes a name,age header row.\n"},
         {"reader.py": "import csv\ndef records(stream):\n    return list(csv.DictReader(stream))\n"},
         _oracle("import io\nfrom reader import records\nassert records(io.StringIO('name,age\\nAda,36\\n')) == [{'name': 'Ada', 'age': '36'}]\n")),
    Case("cache_falsey", "diagnosis", "Cached falsey values are recomputed. Find the cache membership bug and fix it.",
         ("python_compileall", "git_diff_check"), ("cache.py", "tests/*.py", "test_*.py"),
         {"cache.py": "def get(cache, key, build):\n    if not cache.get(key):\n        cache[key] = build()\n    return cache[key]\n"},
         {"cache.py": "def get(cache, key, build):\n    if key not in cache:\n        cache[key] = build()\n    return cache[key]\n"},
         _oracle("from cache import get\ncalled=[]\nassert get({'x': 0}, 'x', lambda: called.append(1)) == 0\nassert called == []\n")),
    Case("rename_greeting", "multi-file", "Rename the public greet function to greeting and update its package export.",
         ("python_compileall", "git_diff_check"), ("hello.py", "api.py", "tests/*.py", "test_*.py"),
         {"hello.py": "def greet(name):\n    return f'Hello, {name}'\n", "api.py": "from hello import greet\n__all__ = ['greet']\n"},
         {"hello.py": "def greeting(name):\n    return f'Hello, {name}'\n", "api.py": "from hello import greeting\n__all__ = ['greeting']\n"},
         _oracle("import api\nassert api.__all__ == ['greeting']\nassert api.greeting('Ada') == 'Hello, Ada'\nassert not hasattr(api, 'greet')\n")),
    Case("timeout_constant", "multi-file", "Change the default timeout to 30 seconds and keep the user-facing documentation accurate.",
         ("python_compileall", "git_diff_check"), ("settings.py", "README.md", "tests/*.py", "test_*.py"),
         {"settings.py": "DEFAULT_TIMEOUT = 10\n", "README.md": "Requests time out after 10 seconds by default.\n"},
         {"settings.py": "DEFAULT_TIMEOUT = 30\n", "README.md": "Requests time out after 30 seconds by default.\n"},
         _oracle("from settings import DEFAULT_TIMEOUT\nassert DEFAULT_TIMEOUT == 30\nassert '30 seconds' in (root / 'README.md').read_text()\n")),
    Case("add_regression_test", "test", "Add a regression test proving normalize trims whitespace. Do not change production code.",
         ("python_unittest", "git_diff_check"), ("tests/test_normalize.py", "test_*.py", "*_test.py", "verify_*.py"),
         {"normalize.py": "def normalize(value):\n    return value.strip().lower()\n", "tests/__init__.py": ""},
         {"tests/test_normalize.py": "import unittest\nfrom normalize import normalize\nclass NormalizeTest(unittest.TestCase):\n    def test_trims_whitespace(self):\n        self.assertEqual(normalize('  Ada  '), 'ada')\n"},
         _oracle("import ast, subprocess\np=root/'tests/test_normalize.py'\nassert p.is_file()\ntext=p.read_text()\ntree=ast.parse(text)\nassert any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value != n.value.strip() for n in ast.walk(tree))\nassert (root/'normalize.py').read_text() == 'def normalize(value):\\n    return value.strip().lower()\\n'\nr=subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=root, text=True, capture_output=True)\nassert r.returncode == 0 and 'Ran 0 tests' not in r.stderr\n")),
    Case("repair_assertion", "test", "Repair the incorrect expectation in the unit test. Production behavior is correct.",
         ("python_unittest", "git_diff_check"), ("tests/test_total.py",),
         {"total.py": "def total(values):\n    return sum(values)\n", "tests/test_total.py": "import unittest\nfrom total import total\nclass TotalTest(unittest.TestCase):\n    def test_total(self): self.assertEqual(total([2, 3]), 6)\n"},
         {"tests/test_total.py": "import unittest\nfrom total import total\nclass TotalTest(unittest.TestCase):\n    def test_total(self): self.assertEqual(total([2, 3]), 5)\n"},
         _oracle("text=(root/'tests/test_total.py').read_text()\nassert 'assertEqual(total([2, 3]), 5)' in text\n")),
    Case("new_version_module", "new-file", "Add version.py defining __version__ as '1.0.0'.",
         ("python_compileall", "git_diff_check"), ("version.py", "tests/*.py", "test_*.py"),
         {"README.md": "Example package.\n"}, {"version.py": "__version__ = '1.0.0'\n"},
         _oracle("from version import __version__\nassert __version__ == '1.0.0'\n")),
    Case("already_correct", "no-op", "Ensure enabled returns a strict boolean for any input. If it already does, make no changes.",
         ("python_compileall", "git_diff_check"), (),
         {"flags.py": "def enabled(value):\n    return bool(value)\n"}, {},
         _oracle("from flags import enabled\nassert enabled([]) is False and enabled([1]) is True\n")),
)


def case_by_id(case_id: str) -> Case:
    return next(case for case in CASES if case.id == case_id)
