"""Explicit-root and exact-path safety helpers."""

from __future__ import annotations

import contextlib
import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator

from .common import fail


WILDCARDS = frozenset("*?[]{}")


@dataclass(frozen=True, slots=True)
class RootContext:
    path: Path
    device: int
    inode: int

    @property
    def identity(self) -> dict[str, int | str]:
        return {"path": str(self.path), "device": self.device, "inode": self.inode}

    @property
    def persistent_identity(self) -> dict[str, int]:
        return {"device": self.device, "inode": self.inode}


def open_root(value: str) -> RootContext:
    if not isinstance(value, str) or not value:
        fail("INVALID_REQUEST", "An explicit absolute root is required")
    raw = Path(value)
    if not raw.is_absolute():
        fail("INVALID_REQUEST", "Root must be absolute")
    try:
        info = raw.lstat()
    except OSError as exc:
        fail("IO_ERROR", f"Cannot inspect root: {exc}", stage="root", retryable=True)
    if stat.S_ISLNK(info.st_mode):
        fail("ROOT_ESCAPE", "Root cannot be a symbolic link", stage="root")
    if not stat.S_ISDIR(info.st_mode):
        fail("INVALID_REQUEST", "Root must be a directory", stage="root")
    resolved = raw.resolve(strict=True)
    final_info = resolved.stat()
    return RootContext(resolved, final_info.st_dev, final_info.st_ino)


def normalize_relative(value: str, *, allow_overseer: bool = True) -> str:
    if not isinstance(value, str) or not value:
        fail("INVALID_REQUEST", "Path must be a non-empty string")
    if "\x00" in value:
        fail("INVALID_REQUEST", "Path contains NUL")
    value = value.replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("/"):
        fail("ROOT_ESCAPE", f"Absolute path is not allowed: {value}")
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        fail("ROOT_ESCAPE", f"Dot and parent segments are not allowed: {value}")
    if any(any(char in WILDCARDS for char in part) for part in parts):
        fail("INVALID_REQUEST", f"Wildcards are not allowed: {value}")
    if any(part.endswith(" ") or part.endswith(".") for part in parts):
        fail("INVALID_REQUEST", f"Platform-reserved path form: {value}")
    if not allow_overseer and parts[0].lower() == "overseer":
        fail("PROTECTED_PATH", f"Overseer-owned path is protected: {value}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        fail("INVALID_REQUEST", "Mutation paths must be valid UTF-8")
    normalized = "/".join(parts)
    if normalized in {"overseer", "overseer.md"} and not allow_overseer:
        fail("PROTECTED_PATH", f"Overseer-owned path is protected: {value}")
    return normalized


def comparison_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def checked_path(root: RootContext, relative: str, *, must_exist: bool = True) -> Path:
    relative = normalize_relative(relative)
    candidate = root.path.joinpath(*relative.split("/"))
    current = root.path
    parts = relative.split("/")
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if must_exist or index < len(parts) - 1:
                fail("IO_ERROR", f"Path does not exist: {relative}", stage="path", retryable=True)
            break
        except OSError as exc:
            fail("IO_ERROR", f"Cannot inspect path: {relative}: {exc}", stage="path", retryable=True)
        if index < len(parts) - 1 and stat.S_ISLNK(info.st_mode):
            fail("ROOT_ESCAPE", f"Parent component is a symbolic link: {relative}")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            fail("IO_ERROR", f"Parent component is not a directory: {relative}", stage="path")
    return candidate


def path_identity(path: Path) -> dict[str, int | str]:
    info = path.lstat()
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": stat.S_IFMT(info.st_mode),
        "size": info.st_size,
    }


def mutation_capability() -> tuple[bool, str]:
    if os.name != "posix":
        return False, "Version 1 mutation requires POSIX descriptor-relative operations"
    required = [os.open, os.stat, os.rename, os.unlink, os.mkdir]
    unsupported = [func.__name__ for func in required if func not in os.supports_dir_fd]
    if unsupported:
        return False, f"Missing dir_fd support: {', '.join(unsupported)}"
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        return False, "Missing O_NOFOLLOW or O_DIRECTORY"
    return True, "descriptor-relative no-follow operations available"


def namespace_collisions(root: RootContext) -> list[str]:
    """Return owner-visible paths that prevent safe initialization."""

    collisions: list[str] = []
    ledger = root.path / "overseer.md"
    namespace = root.path / "overseer"
    if ledger.exists() or ledger.is_symlink():
        collisions.append("overseer.md")
    if namespace.exists() or namespace.is_symlink():
        collisions.append("overseer/")
    return collisions


@contextlib.contextmanager
def secure_parent(
    root: RootContext,
    relative: str,
    *,
    create_parents: bool = False,
    parent_mode: int = 0o700,
) -> Iterator[tuple[int, str]]:
    """Yield an open parent directory descriptor and final basename."""

    relative = normalize_relative(relative)
    parts = relative.split("/")
    descriptors: list[int] = []
    root_fd = os.open(root.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptors.append(root_fd)
    root_info = os.fstat(root_fd)
    if (root_info.st_dev, root_info.st_ino) != (root.device, root.inode):
        os.close(root_fd)
        descriptors.clear()
        fail("ROOT_ESCAPE", "Root identity changed before mutation", stage="mutation")
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            try:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current_fd)
            except FileNotFoundError:
                if not create_parents:
                    fail("IO_ERROR", f"Parent does not exist: {relative}", stage="mutation")
                os.mkdir(part, parent_mode, dir_fd=current_fd)
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current_fd)
            except OSError as exc:
                fail("ROOT_ESCAPE", f"Unsafe parent for {relative}: {exc}", stage="mutation")
            descriptors.append(next_fd)
            current_fd = next_fd
        yield current_fd, parts[-1]
    finally:
        for descriptor in reversed(descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def stat_at(parent_fd: int, name: str) -> os.stat_result:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        fail("IO_ERROR", f"Path disappeared before mutation: {name}", stage="mutation", retryable=True)
