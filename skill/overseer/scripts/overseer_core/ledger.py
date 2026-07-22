"""Deterministic marker-bounded overseer.md renderer."""

from __future__ import annotations

from typing import Any

from .common import digest, fail


OPEN_MARKER = "<!-- overseer:managed schema=1 -->"
CLOSE_MARKER = "<!-- /overseer:managed -->"
MAX_HISTORY = 20
MAX_HISTORY_BYTES = 12 * 1024
MAX_MANAGED_BYTES = 64 * 1024


def merge_ledger(existing: bytes | None, model: dict[str, Any]) -> bytes:
    managed = render_managed(model)
    block = f"{OPEN_MARKER}\n{managed}{CLOSE_MARKER}\n".encode("utf-8")
    if existing is None:
        return block
    try:
        text = existing.decode("utf-8")
    except UnicodeDecodeError:
        fail("LEDGER_CONFLICT", "Existing overseer.md is not UTF-8")
    if text.count(OPEN_MARKER) != 1 or text.count(CLOSE_MARKER) != 1:
        fail("LEDGER_CONFLICT", "overseer.md must contain exactly one valid managed block")
    start = text.index(OPEN_MARKER)
    close_start = text.index(CLOSE_MARKER)
    if close_start < start:
        fail("LEDGER_CONFLICT", "overseer.md managed markers are out of order")
    close_end = close_start + len(CLOSE_MARKER)
    suffix_start = close_end
    if text[suffix_start : suffix_start + 2] == "\r\n":
        suffix_start += 2
    elif text[suffix_start : suffix_start + 1] in {"\n", "\r"}:
        suffix_start += 1
    prefix = existing[: len(text[:start].encode("utf-8"))]
    suffix = existing[len(text[:suffix_start].encode("utf-8")) :]
    return prefix + block + suffix


def extract_managed(existing: bytes) -> bytes:
    try:
        text = existing.decode("utf-8")
    except UnicodeDecodeError:
        fail("LEDGER_CONFLICT", "Existing overseer.md is not UTF-8")
    if text.count(OPEN_MARKER) != 1 or text.count(CLOSE_MARKER) != 1:
        fail("LEDGER_CONFLICT", "overseer.md must contain exactly one valid managed block")
    start = text.index(OPEN_MARKER)
    close = text.index(CLOSE_MARKER)
    if close < start:
        fail("LEDGER_CONFLICT", "overseer.md managed markers are out of order")
    return text[start : close + len(CLOSE_MARKER)].encode("utf-8")


def render_managed(model: dict[str, Any]) -> str:
    allowed = {
        "status", "last_material_review", "last_complete_audit", "resume_from",
        "canonical_context", "open_findings", "history",
    }
    unknown = set(model) - allowed
    if unknown:
        fail("INVALID_REQUEST", f"Unknown ledger model fields: {', '.join(sorted(unknown))}")

    context = [_normalize_context(item) for item in model.get("canonical_context", [])]
    findings = [_normalize_finding(item) for item in model.get("open_findings", [])]
    history = [_normalize_history(item) for item in model.get("history", [])]

    inferred = _status(findings)
    status = model.get("status", inferred)
    if status not in {"CLEAN", "ATTENTION", "BLOCKED"}:
        fail("INVALID_REQUEST", "Ledger status must be CLEAN, ATTENTION, or BLOCKED")
    if status != inferred and not (status == "ATTENTION" and inferred == "CLEAN"):
        fail("INVALID_REQUEST", f"Ledger status {status} contradicts findings status {inferred}")

    context.sort(key=lambda item: (item["scope"].casefold(), item["source"].casefold(), item["id"]))
    severity_order = {"BLOCKED": 0, "ATTENTION": 1}
    findings.sort(key=lambda item: (severity_order[item["severity"]], item["kind"].casefold(), item["subject"].casefold(), item["id"]))
    history.sort(key=lambda item: (item["timestamp"], item["id"]), reverse=True)
    history = _bound_history(history)

    last_review = _text(model.get("last_material_review", "never"), 40)
    last_audit = _text(model.get("last_complete_audit", "never"), 40)
    resume = _text(model.get("resume_from", "none"), 500)

    lines = [
        "# Overseer",
        "",
        f"Project context health: {status}",
        f"Last material review: {last_review}",
        f"Last complete audit: {last_audit}",
        f"Resume from: {resume}",
        "",
        "## Canonical context",
        "",
        "| ID | Subject | Authoritative source | Scope | Evidence | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if context:
        for item in context:
            lines.append("| " + " | ".join(_cell(item[key]) for key in ("id", "subject", "source", "scope", "evidence", "status")) + " |")
    else:
        lines.append("| None | None | None | None | None | None |")

    lines.extend([
        "",
        "## Open findings",
        "",
        "| ID | Severity | Kind | Subject | Evidence | Required resolution |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    if findings:
        for item in findings:
            lines.append("| " + " | ".join(_cell(item[key]) for key in ("id", "severity", "kind", "subject", "evidence", "resolution")) + " |")
    else:
        lines.append("| None | None | None | None | None | None |")

    lines.extend(["", "## Recent material history", ""])
    if history:
        for item in history:
            lines.append(f"- {item['timestamp']} `{item['id']}`: {item['summary']}")
    else:
        lines.append("- None")
    managed = "\n".join(lines) + "\n"
    if len(managed.encode("utf-8")) > MAX_MANAGED_BYTES:
        fail("LEDGER_LIMIT_EXCEEDED", "Rendered ledger managed block exceeds 64 KiB")
    return managed


def context_id(subject_key: str) -> str:
    return digest("context", subject_key)[:16]


def finding_id(kind: str, subject: str, source: str) -> str:
    return digest("finding", f"{kind}\0{subject}\0{source}")[:16]


def event_id(transaction_id: str, plan_digest: str) -> str:
    return digest("event", f"{transaction_id}\0{plan_digest}")[:16]


def _normalize_context(item: dict[str, Any]) -> dict[str, str]:
    required = {"subject", "source", "scope", "evidence", "status"}
    if not isinstance(item, dict) or not required.issubset(item):
        fail("INVALID_REQUEST", "Canonical context entry is missing required fields")
    subject = _text(item["subject"], 300)
    source = _text(item["source"], 300)
    value = {
        "id": _text(item.get("id", context_id(f"{subject}\0{source}")), 32),
        "subject": subject,
        "source": source,
        "scope": _text(item["scope"], 200),
        "evidence": _text(item["evidence"], 500),
        "status": _text(item["status"], 80),
    }
    return value


def _normalize_finding(item: dict[str, Any]) -> dict[str, str]:
    required = {"severity", "kind", "subject", "evidence", "resolution"}
    if not isinstance(item, dict) or not required.issubset(item):
        fail("INVALID_REQUEST", "Finding entry is missing required fields")
    severity = item["severity"]
    if severity not in {"ATTENTION", "BLOCKED"}:
        fail("INVALID_REQUEST", "Finding severity must be ATTENTION or BLOCKED")
    kind = _text(item["kind"], 100)
    subject = _text(item["subject"], 300)
    source = _text(item.get("source", "repository evidence"), 300)
    return {
        "id": _text(item.get("id", finding_id(kind, subject, source)), 32),
        "severity": severity,
        "kind": kind,
        "subject": subject,
        "evidence": _text(item["evidence"], 500),
        "resolution": _text(item["resolution"], 500),
    }


def _normalize_history(item: dict[str, Any]) -> dict[str, str]:
    if not isinstance(item, dict) or not {"timestamp", "summary"}.issubset(item):
        fail("INVALID_REQUEST", "History entry is missing timestamp or summary")
    timestamp = _text(item["timestamp"], 40)
    summary = _text(item["summary"], 500)
    return {
        "id": _text(item.get("id", digest("history", f"{timestamp}\0{summary}")[:16]), 32),
        "timestamp": timestamp,
        "summary": summary,
    }


def _bound_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    used = 0
    for item in history[:MAX_HISTORY]:
        size = len(f"- {item['timestamp']} `{item['id']}`: {item['summary']}\n".encode("utf-8"))
        if used + size > MAX_HISTORY_BYTES:
            break
        result.append(item)
        used += size
    return result


def _status(findings: list[dict[str, str]]) -> str:
    if any(item["severity"] == "BLOCKED" for item in findings):
        return "BLOCKED"
    if findings:
        return "ATTENTION"
    return "CLEAN"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        fail("INVALID_REQUEST", "Ledger values must be strings")
    compact = " ".join(value.split())
    if len(compact) > limit:
        fail("LEDGER_LIMIT_EXCEEDED", f"Ledger value exceeds {limit} characters")
    return compact or "none"
