from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


class ReviewError(ValueError):
    """Raised when a review request cannot be safely evaluated."""


MAX_OUTPUT = 65_536
CHECKS: dict[str, tuple[str, ...]] = {
    "git_diff_check": ("git", "diff", "--check"),
    "python_unittest": (sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"),
    "python_compileall": (
        sys.executable,
        "-B",
        "-c",
        "import pathlib; [compile(p.read_bytes(), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py') if '.git' not in p.parts]",
    ),
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_+/.-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim(value: str) -> str:
    return value if len(value) <= MAX_OUTPUT else value[:MAX_OUTPUT] + "\n...[truncated]"


def _run(root: Path, argv: Sequence[str], timeout: int = 300, *, binary: bool = False) -> subprocess.CompletedProcess[Any]:
    env = os.environ.copy()
    env.update({"GIT_OPTIONAL_LOCKS": "0", "PYTHONDONTWRITEBYTECODE": "1"})
    env.setdefault("UV_CACHE_DIR", str(root.parent / ".ci-uv-cache"))
    env.setdefault("UV_PYTHON_INSTALL_DIR", str(root.parent / ".ci-uv-python"))
    return subprocess.run(
        list(argv), cwd=root, stdin=subprocess.DEVNULL, capture_output=True,
        text=not binary, timeout=timeout, check=False, shell=False, env=env,
    )


def check_command(root: Path, check_id: str) -> tuple[str, ...]:
    """Resolve a trusted check ID using the reviewed repository's declared tooling."""
    if check_id != "python_unittest":
        return CHECKS[check_id]
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return CHECKS[check_id]
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return CHECKS[check_id]
    if "pytest" not in project.get("tool", {}):
        return CHECKS[check_id]
    uv = shutil.which("uv") or "uv"
    basetemp = root.parent / f".ci-pytest-{root.name}-{uuid.uuid4().hex}"
    return (
        uv, "run", "--isolated", "--project", ".", "--extra", "dev", "--python", "3.12",
        "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", "--basetemp", str(basetemp),
    )


def _git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess[Any]:
    try:
        result = _run(root, ("git", *args), binary=binary)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewError(f"Git command unavailable: {type(exc).__name__}") from exc
    if result.returncode:
        error = result.stderr.decode(errors="replace") if binary else result.stderr
        raise ReviewError(f"Git inspection failed: {_trim(error).strip()}")
    return result


def validate_workspace(path: Path) -> Path:
    root = path.resolve()
    if not root.is_dir():
        raise ReviewError("workspace does not exist")
    reported = Path(_git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if reported != root:
        raise ReviewError("workspace must be the Git worktree root")
    return root


def canonical_patch(root: Path) -> str:
    patch = _git(root, "diff", "--no-ext-diff", "--binary", "HEAD", "--").stdout
    raw = _git(root, "ls-files", "--others", "--exclude-standard", "-z", binary=True).stdout
    for encoded in sorted(item for item in raw.split(b"\0") if item):
        relative = encoded.decode("utf-8", errors="surrogateescape")
        result = _run(root, ("git", "diff", "--no-index", "--binary", "--", "/dev/null", relative))
        if result.returncode not in (0, 1):
            raise ReviewError(f"unable to capture untracked path: {relative}")
        patch += result.stdout
    return patch


def changed_paths(root: Path) -> list[str]:
    raw = _git(root, "diff", "--name-status", "-z", "--find-renames", "HEAD", "--", binary=True).stdout
    tokens = [item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item]
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        count = 2 if status[:1] in {"R", "C"} else 1
        paths.extend(tokens[index + 1:index + 1 + count])
        index += 1 + count
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z", binary=True).stdout
    paths.extend(item.decode("utf-8", errors="surrogateescape") for item in untracked.split(b"\0") if item)
    return sorted(set(path.replace("\\", "/") for path in paths))


def state_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(_git(root, "rev-parse", "HEAD").stdout.encode())
    digest.update(_git(root, "diff", "--cached", "--binary", "HEAD", "--").stdout.encode())
    digest.update(canonical_patch(root).encode("utf-8", errors="surrogateescape"))
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        name = relative.as_posix().encode("utf-8", errors="surrogateescape")
        digest.update(name + b"\0")
        if path.is_symlink():
            digest.update(b"L" + os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            digest.update(b"F" + str(path.stat().st_size).encode() + b"\0")
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        elif path.is_dir():
            digest.update(b"D")
    return digest.hexdigest()


def _finding(code: str, message: str, path: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "severity": "blocking", "message": message}
    if path is not None:
        value["path"] = path
    return value


def _allowed(path: str, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        token = "\0DOUBLE_STAR\0"
        expression = re.escape(pattern.replace("**", token))
        expression = expression.replace(r"\*", "[^/]*").replace(re.escape(token), ".*")
        if re.fullmatch(expression, path) or (pattern.endswith("/**") and path == pattern[:-3]):
            return True
    return False


def load_job(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"invalid job record: {type(exc).__name__}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not re.fullmatch(r"[0-9a-f]{32}", value["id"]):
        raise ReviewError("job record requires a 32-character lowercase hexadecimal id")
    if value.get("status") != "completed" or not isinstance(value.get("diff"), str):
        raise ReviewError("job record must be completed and contain diff evidence")
    return value


def review(job_path: Path, workspace: Path, allow_paths: Sequence[str], checks: Sequence[str], output: Path) -> dict[str, Any]:
    root = validate_workspace(workspace)
    if not allow_paths or any(not item or Path(item).is_absolute() or ".." in Path(item).parts for item in allow_paths):
        raise ReviewError("allow paths must be nonempty relative patterns")
    if len(set(checks)) != len(checks) or any(item not in CHECKS for item in checks):
        raise ReviewError("checks must be unique trusted check IDs")
    destination = output.resolve()
    if destination == root or root in destination.parents:
        raise ReviewError("output must be outside the reviewed workspace")
    if destination.exists():
        raise ReviewError("output already exists")
    job = load_job(job_path)
    started_at = _now()
    before = state_fingerprint(root)
    patch = canonical_patch(root)
    paths = changed_paths(root)
    findings: list[dict[str, Any]] = []
    if patch != job["diff"]:
        findings.append(_finding("PATCH_MISMATCH", "Workspace patch does not match worker evidence."))
    for path in paths:
        if not _allowed(path, allow_paths):
            findings.append(_finding("PATH_OUT_OF_SCOPE", "Changed path is outside the authorized scope.", path))
    if "GIT binary patch" in patch or "Binary files " in patch:
        findings.append(_finding("BINARY_CHANGE", "Binary changes are not supported by this review gate."))
    added = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    if any(pattern.search(added) for pattern in SECRET_PATTERNS):
        findings.append(_finding("LIKELY_CREDENTIAL", "Patch contains a likely credential or private key."))
    results: list[dict[str, Any]] = []
    for check_id in checks:
        began = time.monotonic()
        try:
            process = _run(root, check_command(root, check_id))
            status = "passed" if process.returncode == 0 else "failed"
            output_text = process.stdout + process.stderr
            if check_id == "python_unittest" and re.search(r"Ran 0 tests?", output_text):
                status = "failed"
                output_text += "\nCheck failed: unittest discovery found zero tests.\n"
            exit_code: int | None = process.returncode
        except subprocess.TimeoutExpired as exc:
            status, exit_code, output_text = "timeout", None, str(exc)
        except OSError as exc:
            status, exit_code, output_text = "unavailable", None, str(exc)
        results.append({"id": check_id, "status": status, "exit_code": exit_code,
                        "duration_ms": round((time.monotonic() - began) * 1000), "output": _trim(output_text)})
        if status != "passed":
            findings.append(_finding("CHECK_FAILED", f"Trusted check {check_id} ended with status {status}."))
    after = state_fingerprint(root)
    if before != after:
        findings.append(_finding("REVIEW_MUTATED_WORKSPACE", "Repository state changed while review checks ran."))
    artifact = {
        "schema_version": 1, "review_id": uuid.uuid4().hex, "worker_job_id": job["id"],
        "started_at": started_at, "finished_at": _now(),
        "verdict": "request_changes" if any(item["severity"] == "blocking" for item in findings) else "approve",
        "patch_sha256": hashlib.sha256(patch.encode("utf-8", errors="surrogateescape")).hexdigest(),
        "changed_paths": paths, "findings": findings, "checks": results,
        "state_before": before, "state_after": after,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(artifact, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ReviewError("output already exists") from exc
    return artifact
