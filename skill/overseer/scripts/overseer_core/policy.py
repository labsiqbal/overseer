"""Conservative content classification and operation policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from .common import digest, fail
from .paths import normalize_relative


DEFAULT_LIMITS: dict[str, int] = {
    "max_files": 100_000,
    "max_total_bytes": 50_000_000_000,
    "max_text_bytes": 1_048_576,
    "max_git_bytes": 4_194_304,
    "max_findings": 5_000,
    "max_scan_paths": 500,
    "max_scan_hops": 2,
}

SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks")
SOURCE_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java",
    ".kt", ".kts", ".rb", ".php", ".c", ".h", ".cc", ".cpp", ".cs",
    ".swift", ".scala", ".sh", ".bash", ".zsh", ".fish", ".sql", ".vue",
    ".svelte", ".css", ".scss", ".less", ".html", ".xml",
}
BUSINESS_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".mov",
    ".mp3", ".wav", ".zip", ".tar", ".gz", ".jsonl", ".parquet",
}
LIVING_NAMES = {
    "agents.md", "claude.md", "readme.md", "readme", "contributing.md",
    "security.md", "runbook.md", "operations.md",
}
HISTORICAL_PARTS = {"adr", "adrs", "decisions", "history", "release-notes", "audit-logs"}
GENERATED_PARTS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build", "target",
    ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    ".next", ".nuxt", "coverage",
}
LOCK_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "uv.lock",
    "poetry.lock", "cargo.lock", "gemfile.lock", "composer.lock",
}


@dataclass(frozen=True, slots=True)
class Classification:
    content_class: str
    rule_id: str
    confidence: str
    reason: str
    secret: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "class": self.content_class,
            "rule_id": self.rule_id,
            "confidence": self.confidence,
            "reason": self.reason,
            "secret": self.secret,
        }


@dataclass(slots=True)
class Policy:
    exact_exclusions: set[str]
    path_classes: dict[str, str]
    limits: dict[str, int]

    @classmethod
    def default(cls) -> "Policy":
        return cls(set(), {}, dict(DEFAULT_LIMITS))

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "Policy":
        if value is None:
            return cls.default()
        allowed = {"protocol", "exact_exclusions", "path_classes", "limits"}
        unknown = set(value) - allowed
        if unknown:
            fail("INVALID_REQUEST", f"Unknown policy fields: {', '.join(sorted(unknown))}")
        if value.get("protocol", 1) != 1:
            fail("UNSUPPORTED_PROTOCOL", "Policy protocol must be 1")
        exclusions: set[str] = set()
        for path in value.get("exact_exclusions", []):
            exclusions.add(normalize_relative(path, allow_overseer=False))
        classes: dict[str, str] = {}
        allowed_classes = {"living_context", "historical_record", "business_artifact"}
        for path, content_class in value.get("path_classes", {}).items():
            normalized = normalize_relative(path, allow_overseer=False)
            if content_class not in allowed_classes:
                fail("INVALID_REQUEST", f"Policy cannot assign class {content_class}")
            hard = classify_path(normalized, None)
            if hard.content_class in {"secret", "generated", "source_code"}:
                fail("PROTECTED_PATH", f"Policy cannot reclassify protected path: {normalized}")
            classes[normalized] = content_class
        limits = dict(DEFAULT_LIMITS)
        for key, value_limit in value.get("limits", {}).items():
            if key not in DEFAULT_LIMITS or not isinstance(value_limit, int) or value_limit <= 0:
                fail("INVALID_REQUEST", f"Invalid policy limit: {key}")
            limits[key] = min(value_limit, DEFAULT_LIMITS[key])
        return cls(exclusions, classes, limits)

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": 1,
            "exact_exclusions": sorted(self.exact_exclusions),
            "path_classes": dict(sorted(self.path_classes.items())),
            "limits": dict(sorted(self.limits.items())),
        }

    @property
    def policy_digest(self) -> str:
        return digest("policy", self.as_dict())

    def classify(self, relative: str, mode: int | None = None) -> Classification:
        normalized = normalize_relative(relative)
        hard = classify_path(normalized, mode)
        if hard.content_class in {"secret", "generated", "source_code", "unsupported"}:
            return hard
        override = self.path_classes.get(normalized)
        if override:
            return Classification(override, "owner_exact_override", "high", "Owner-approved exact path class")
        return hard


def classify_path(relative: str, mode: int | None) -> Classification:
    import stat

    normalized = normalize_relative(relative)
    path = PurePosixPath(normalized)
    lowered_parts = tuple(part.lower() for part in path.parts)
    name = path.name.lower()
    suffix = path.suffix.lower()

    if mode is not None:
        if stat.S_ISLNK(mode):
            return Classification("symlink", "object_symlink", "high", "Symbolic link, never followed")
        if stat.S_ISDIR(mode):
            return Classification("directory", "object_directory", "high", "Directory")
        if not stat.S_ISREG(mode):
            return Classification("unsupported", "object_special", "high", "Unsupported filesystem object")

    if name in SECRET_NAMES or suffix in SECRET_SUFFIXES or any("secret" in part or "credential" in part for part in lowered_parts):
        return Classification("secret", "hard_secret_name", "high", "Secret-bearing name pattern", True)
    if any(part in GENERATED_PARTS for part in lowered_parts) or name in LOCK_NAMES:
        return Classification("generated", "generated_or_lock_path", "high", "Generated, vendor, cache, or lock path")
    if name == "changelog.md" or name.startswith("changelog."):
        return Classification("generated", "protected_changelog", "high", "Changelog is protected from manual maintenance")
    if suffix in SOURCE_SUFFIXES:
        return Classification("source_code", "source_extension", "high", "Source code extension")
    if any(part in HISTORICAL_PARTS for part in lowered_parts) or name.startswith("adr-"):
        return Classification("historical_record", "historical_path", "medium", "Historical record convention")
    if name in LIVING_NAMES or suffix == ".md":
        return Classification("living_context", "living_markdown", "high", "Human-maintained Markdown context")
    if suffix in BUSINESS_SUFFIXES:
        return Classification("business_artifact", "artifact_extension", "medium", "Recognized project artifact extension")
    return Classification("unknown", "conservative_unknown", "low", "No high-confidence class rule matched")


def is_default_excluded(relative: str) -> bool:
    parts = tuple(part.lower() for part in PurePosixPath(relative).parts)
    if parts and parts[0] == "overseer":
        if len(parts) == 1:
            return False
        if parts[1] in {"archive", "transactions"} or parts[1] in {"state.json", "policy.json", ".lock"}:
            return True
    return any(part in GENERATED_PARTS for part in parts)


def can_operation(content_class: str, primitive: str, relative: str) -> bool:
    if primitive == "WriteLedger":
        return relative == "overseer.md"
    if primitive == "WritePolicy":
        return relative == "overseer/policy.json"
    if primitive == "EditLivingDocument":
        return content_class == "living_context"
    if primitive in {"MoveExactPath", "ArchiveExactPath"}:
        return content_class in {"living_context", "historical_record", "business_artifact", "unknown", "symlink"}
    return False


def safe_path_label(relative: str, classification: Classification | None = None) -> str:
    value = classification or classify_path(relative, None)
    if value.secret:
        return f"[secret-path:{digest('secret-path', relative)[:16]}]"
    return relative
