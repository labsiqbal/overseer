"""Bounded, deterministic repository evidence capture."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from collections import deque
from pathlib import Path
from typing import Any, Iterable

from .common import digest, fail, sha256_file
from .paths import RootContext, checked_path, normalize_relative
from .policy import Policy, is_default_excluded, safe_path_label


def inventory(
    root: RootContext,
    policy: Policy,
    *,
    mode: str,
    session_paths: Iterable[str] = (),
    referenced_paths: Iterable[str] = (),
) -> dict[str, Any]:
    if mode not in {"scan", "audit"}:
        fail("INVALID_REQUEST", f"Unsupported inspection mode: {mode}")
    if mode == "audit":
        candidates, boundary_warnings = _walk(root, policy)
        scope: dict[str, Any] = {"mode": "audit"}
    else:
        normalized_session = sorted({normalize_relative(path) for path in session_paths})
        normalized_referenced = sorted({normalize_relative(path) for path in referenced_paths})
        candidates, boundary_warnings = _scan_closure(root, policy, normalized_session, normalized_referenced)
        scope = {"mode": "scan", "session_paths": normalized_session, "referenced_paths": normalized_referenced}

    records: list[dict[str, Any]] = []
    total_bytes = 0
    coverage = "complete"
    warnings = list(boundary_warnings)
    for relative in sorted(candidates):
        if len(records) >= policy.limits["max_files"]:
            coverage = "limit_exceeded"
            warnings.append("File count limit reached")
            break
        preliminary = policy.classify(relative)
        label = safe_path_label(relative, preliminary)
        try:
            path = checked_path(root, relative)
            info = path.lstat()
        except Exception as exc:
            if hasattr(exc, "code"):
                warnings.append(f"Unreadable path omitted: {label}")
                coverage = "partial"
                continue
            raise
        classification = policy.classify(relative, info.st_mode)
        if relative in policy.exact_exclusions:
            continue
        record: dict[str, Any] = {
            "type": _type_name(info.st_mode),
            "size": info.st_size,
            "classification": classification.as_dict(),
        }
        if classification.secret:
            record["path"] = None
            record["path_digest"] = digest("secret-path", relative)
        else:
            record["path"] = relative
        if stat.S_ISREG(info.st_mode):
            total_bytes += info.st_size
            if total_bytes > policy.limits["max_total_bytes"]:
                coverage = "limit_exceeded"
                warnings.append("Total byte limit reached")
                break
            if classification.secret:
                record["sha256"] = _local_hash(path)
            else:
                try:
                    record["sha256"] = sha256_file(str(path))
                except OSError:
                    record["sha256"] = None
                    coverage = "partial"
                    warnings.append(f"Could not hash: {label}")
        elif stat.S_ISLNK(info.st_mode):
            try:
                target = os.readlink(path)
                record["link_target_digest"] = hashlib.sha256(os.fsencode(target)).hexdigest()
            except OSError:
                record["link_target_digest"] = None
                coverage = "partial"
        records.append(record)

    git = git_evidence(root, policy, policy.limits["max_git_bytes"])
    snapshot_payload = {
        "root_identity": root.identity,
        "policy_digest": policy.policy_digest,
        "mode": mode,
        "scope": scope,
        "coverage": coverage,
        "records": records,
        "git": git,
    }
    return {
        **snapshot_payload,
        "warnings": sorted(set(warnings)),
        "snapshot_digest": digest("snapshot", snapshot_payload),
    }


def git_evidence(root: RootContext, policy: Policy, max_bytes: int) -> dict[str, Any]:
    command = ["git", "-C", str(root.path), "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching", "--no-renames"]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=10,
            env={"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "git unavailable", "changes": []}
    if completed.returncode != 0:
        return {"available": False, "reason": "not a Git worktree", "changes": []}
    output = completed.stdout[: max_bytes + 1]
    truncated = len(output) > max_bytes
    if truncated:
        output = output[:max_bytes]
    changes: list[dict[str, str]] = []
    for entry in output.rstrip(b"\0").split(b"\0"):
        if len(entry) < 4:
            continue
        status_code = entry[:2].decode("ascii", "replace")
        path = entry[3:].decode("utf-8", "surrogateescape")
        try:
            normalized = normalize_relative(path)
        except Exception:
            normalized = "[unsupported-path]"
        classification = policy.classify(normalized) if normalized != "[unsupported-path]" else None
        if normalized != "[unsupported-path]" and is_default_excluded(normalized):
            continue
        changes.append({"status": status_code, "path": safe_path_label(normalized, classification) if classification else normalized})
    return {"available": True, "truncated": truncated, "changes": sorted(changes, key=lambda item: (item["path"], item["status"]))}


def markdown_references(text: str) -> set[str]:
    """Conservatively collect relative Markdown link destinations."""

    import re

    found: set[str] = set()
    patterns = [
        r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)",
        r"^\s*\[[^\]]+\]:\s*(\S+)",
        r"`([^`\n]+)`",
    ]
    for index, pattern in enumerate(patterns):
        flags = re.MULTILINE if index == 1 else 0
        for match in re.finditer(pattern, text, flags):
            target = match.group(1).strip("<>")
            if index == 2:
                if any(char.isspace() for char in target):
                    continue
                leaf = target.rstrip("/").rsplit("/", 1)[-1]
                if "/" not in target and "." not in leaf:
                    continue
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            if not path_part or "://" in path_part or path_part.startswith(("/", "mailto:")):
                continue
            try:
                found.add(normalize_relative(path_part))
            except Exception:
                continue
    return found


def find_exact_references(root: RootContext, policy: Policy, old_path: str) -> list[str]:
    needle = old_path.encode("utf-8")
    matches: list[str] = []
    candidates, _ = _walk(root, policy)
    for relative in candidates:
        classification = policy.classify(relative)
        if classification.content_class not in {"living_context", "historical_record", "source_code"}:
            continue
        path = root.path.joinpath(*relative.split("/"))
        try:
            if path.stat().st_size > policy.limits["max_text_bytes"]:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if needle in data:
            matches.append(relative)
    return sorted(matches)


def _scan_closure(
    root: RootContext,
    policy: Policy,
    session_paths: Iterable[str],
    referenced_paths: Iterable[str],
) -> tuple[set[str], list[str]]:
    initial = {normalize_relative(path) for path in [*session_paths, *referenced_paths]}
    queue: deque[tuple[str, int]] = deque((path, 0) for path in sorted(initial))
    seen: set[str] = set()
    warnings: list[str] = []
    while queue:
        relative, hop = queue.popleft()
        if relative in seen:
            continue
        if len(seen) >= policy.limits["max_scan_paths"]:
            warnings.append("Scan closure path limit reached")
            break
        seen.add(relative)
        path = root.path.joinpath(*relative.split("/"))
        if path.suffix.lower() != ".md" or hop >= policy.limits["max_scan_hops"]:
            continue
        try:
            if path.stat().st_size > policy.limits["max_text_bytes"]:
                warnings.append(f"Markdown too large for closure: {relative}")
                continue
            text = path.read_text("utf-8")
        except (OSError, UnicodeError):
            warnings.append(f"Markdown unreadable for closure: {relative}")
            continue
        base = PurePathParent(relative)
        for target in markdown_references(text):
            combined = _resolve_markdown_target(base, target)
            if combined and combined not in seen:
                queue.append((combined, hop + 1))
    for common in ("AGENTS.md", "CLAUDE.md", "README.md", "overseer.md"):
        if (root.path / common).is_file():
            seen.add(common)
    return seen, warnings


def _walk(root: RootContext, policy: Policy) -> tuple[set[str], list[str]]:
    candidates: set[str] = set()
    warnings: list[str] = []
    for current, directories, files in os.walk(root.path, topdown=True, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(root.path).as_posix()
        kept: list[str] = []
        for directory in sorted(directories):
            relative = directory if relative_dir == "." else f"{relative_dir}/{directory}"
            if is_default_excluded(relative) or relative in policy.exact_exclusions:
                continue
            path = current_path / directory
            try:
                if path.is_symlink():
                    candidates.add(relative)
                    continue
            except OSError:
                warnings.append(f"Unreadable directory boundary: {relative}")
                continue
            if (path / ".git").exists() and path != root.path:
                warnings.append(f"Nested repository boundary: {relative}")
                candidates.add(relative)
                continue
            kept.append(directory)
            candidates.add(relative)
        directories[:] = kept
        for filename in sorted(files):
            relative = filename if relative_dir == "." else f"{relative_dir}/{filename}"
            if is_default_excluded(relative) or relative in policy.exact_exclusions:
                continue
            candidates.add(relative)
    return candidates, warnings


def _local_hash(path: Path) -> str | None:
    try:
        return sha256_file(str(path))
    except OSError:
        return None


def _type_name(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "unsupported"


def PurePathParent(relative: str) -> str:
    parent = Path(relative).parent.as_posix()
    return "" if parent == "." else parent


def _resolve_markdown_target(base: str, target: str) -> str | None:
    raw = Path(base, target) if base else Path(target)
    parts: list[str] = []
    for part in raw.as_posix().split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        return None
    try:
        return normalize_relative("/".join(parts))
    except Exception:
        return None
