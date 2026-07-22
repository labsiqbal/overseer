"""Canonical protocol utilities and stable failures."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, NoReturn


PROTOCOL_VERSION = 1


@dataclass(slots=True)
class OverseerError(Exception):
    code: str
    message: str
    stage: str = "validation"
    retryable: bool = False
    recovery_status: str = "none"
    details: dict[str, Any] | None = None

    def as_details(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "retryable": self.retryable,
            "recovery_status": self.recovery_status,
        }
        if self.details:
            value["context"] = self.details
        return value


def fail(
    code: str,
    message: str,
    *,
    stage: str = "validation",
    retryable: bool = False,
    recovery_status: str = "none",
    details: dict[str, Any] | None = None,
) -> NoReturn:
    raise OverseerError(code, message, stage, retryable, recovery_status, details)


def canonical_json_bytes(value: Any) -> bytes:
    _reject_floats(value)
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return text.encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError) as exc:
        fail("INVALID_REQUEST", f"Value is not canonical JSON: {exc}")


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def digest(domain: str, value: Any) -> str:
    prefix = f"overseer:{domain}:v{PROTOCOL_VERSION}\0".encode("ascii")
    return hashlib.sha256(prefix + canonical_json_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str, *, chunk_size: int = 1024 * 1024) -> str:
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            value.update(chunk)
    return value.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        fail("INVALID_REQUEST", "Timestamp must be an RFC 3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail("INVALID_REQUEST", f"Invalid RFC 3339 timestamp: {value}")
    if parsed.tzinfo is None:
        fail("INVALID_REQUEST", "Timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def require_fields(value: dict[str, Any], *, required: set[str], optional: set[str] | None = None) -> None:
    if not isinstance(value, dict):
        fail("INVALID_REQUEST", "Request must be a JSON object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - (optional or set()))
    if missing:
        fail("INVALID_REQUEST", f"Missing fields: {', '.join(missing)}")
    if unknown:
        fail("INVALID_REQUEST", f"Unknown fields: {', '.join(unknown)}")


def _reject_floats(value: Any) -> None:
    if isinstance(value, float):
        fail("INVALID_REQUEST", "Floats are prohibited in canonical JSON")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                fail("INVALID_REQUEST", "JSON object keys must be strings")
            _reject_floats(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_floats(item)
