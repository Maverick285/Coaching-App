"""Markdown file operations on the memory directory, with git-backed history."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from git import Actor, InvalidGitRepositoryError, Repo

from buddy.config import get_settings
from buddy.memory.schemas import SEED_FILES, DocumentType, classify_path


class MemoryPathError(ValueError):
    """Raised on unsafe path operations."""


@dataclass
class FileMeta:
    rel_path: str
    abs_path: Path
    document_type: DocumentType
    size_bytes: int
    last_modified: datetime
    content_hash: str


class MemoryStore:
    """Owns the memory/ directory and its git repo.

    All paths supplied externally are treated as untrusted; resolution is
    done relative to the configured root and any escape attempt raises
    `MemoryPathError`.
    """

    def __init__(self, root: Path | None = None):
        settings = get_settings()
        self.root = Path(root) if root else Path(settings.memory_path)
        self.user_name = settings.user_name
        self.persona_name = settings.persona_name
        self._actor = Actor("Buddy", "buddy@localhost")
        self._ensure_root()
        self._repo = self._ensure_repo()
        self._ensure_seed_files()

    # ---- bootstrap -------------------------------------------------------

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "days").mkdir(exist_ok=True)
        (self.root / "episodes").mkdir(exist_ok=True)
        (self.root / "conversations").mkdir(exist_ok=True)

    def _ensure_repo(self) -> Repo:
        try:
            return Repo(self.root)
        except InvalidGitRepositoryError:
            repo = Repo.init(self.root)
            with repo.config_writer() as cw:
                cw.set_value("user", "name", "Buddy")
                cw.set_value("user", "email", "buddy@localhost")
                cw.set_value("commit", "gpgsign", "false")
            return repo

    def _ensure_seed_files(self) -> None:
        wrote_any = False
        for name, template in SEED_FILES.items():
            path = self.root / name
            if path.exists():
                continue
            content = template.format(
                user_name=self.user_name,
                persona_name=self.persona_name,
            )
            path.write_text(content, encoding="utf-8")
            wrote_any = True
        if wrote_any:
            self._git_commit_all("memory: seed initial files")

    # ---- path safety -----------------------------------------------------

    def resolve(self, rel_path: str) -> Path:
        # Reject absolute paths (POSIX or Windows) before any normalization.
        if os.path.isabs(rel_path) or rel_path.startswith("/"):
            raise MemoryPathError(f"Refusing absolute path: {rel_path!r}")
        if ".." in Path(rel_path).parts:
            raise MemoryPathError(f"Refusing path with parent traversal: {rel_path!r}")
        candidate = (self.root / rel_path).resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError as exc:
            raise MemoryPathError(f"Path escapes memory root: {rel_path!r}") from exc
        return candidate

    def relpath_of(self, abs_path: Path) -> str:
        return str(abs_path.resolve().relative_to(self.root.resolve())).replace(os.sep, "/")

    # ---- read / write ----------------------------------------------------

    def read(self, rel_path: str) -> str:
        path = self.resolve(rel_path)
        if not path.exists():
            raise FileNotFoundError(rel_path)
        return path.read_text(encoding="utf-8")

    def write(self, rel_path: str, content: str, *, commit_message: str | None = None) -> FileMeta:
        path = self.resolve(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        msg = commit_message or f"memory: update {rel_path}"
        self._git_commit_paths([rel_path], msg)
        return self.stat(rel_path)

    def append(self, rel_path: str, content: str, *, commit_message: str | None = None) -> FileMeta:
        path = self.resolve(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(content)
        self._git_commit_paths([rel_path], commit_message or f"memory: append {rel_path}")
        return self.stat(rel_path)

    def delete(self, rel_path: str, *, commit_message: str | None = None) -> None:
        path = self.resolve(rel_path)
        if path.exists():
            path.unlink()
            self._git_commit_paths([rel_path], commit_message or f"memory: delete {rel_path}")

    def exists(self, rel_path: str) -> bool:
        try:
            return self.resolve(rel_path).exists()
        except MemoryPathError:
            return False

    def stat(self, rel_path: str) -> FileMeta:
        path = self.resolve(rel_path)
        st = path.stat()
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        return FileMeta(
            rel_path=rel_path,
            abs_path=path,
            document_type=classify_path(rel_path),
            size_bytes=st.st_size,
            last_modified=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    # ---- listing ---------------------------------------------------------

    def iter_files(self) -> list[FileMeta]:
        results: list[FileMeta] = []
        for abs_path in self.root.rglob("*.md"):
            if ".git" in abs_path.parts:
                continue
            rel = self.relpath_of(abs_path)
            try:
                results.append(self.stat(rel))
            except (FileNotFoundError, MemoryPathError):
                continue
        results.sort(key=lambda m: m.rel_path)
        return results

    # ---- git -------------------------------------------------------------

    def _git_commit_paths(self, rel_paths: list[str], message: str) -> None:
        try:
            self._repo.index.add(rel_paths)
            if self._repo.is_dirty(index=True, working_tree=False, untracked_files=False):
                self._repo.index.commit(message, author=self._actor, committer=self._actor)
        except Exception:
            # Best-effort: even if a commit fails, the filesystem write succeeded.
            # The next operation will pick up the leftover changes.
            pass

    def _git_commit_all(self, message: str) -> None:
        try:
            self._repo.git.add(A=True)
            if self._repo.is_dirty(index=True, working_tree=False, untracked_files=False):
                self._repo.index.commit(message, author=self._actor, committer=self._actor)
        except Exception:
            pass

    def repo_status(self) -> str:
        try:
            if self._repo.is_dirty(untracked_files=True):
                return "dirty"
            return "clean"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"

    def push_to_remote(self) -> str:
        settings = get_settings()
        if not settings.git_remote:
            return "no remote configured"
        try:
            if "backup" not in [r.name for r in self._repo.remotes]:
                self._repo.create_remote("backup", settings.git_remote)
            backup = self._repo.remote("backup")
            backup.push("HEAD")
            return "pushed"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"

    # ---- convenience: day file -----------------------------------------

    def day_file_path(self, date_str: str) -> str:
        return f"days/{date_str}.md"

    def conversation_log_path(self, date_str: str, session_label: str) -> str:
        return f"conversations/{date_str}/{session_label}.md"

    def episode_path(self, date_str: str, slug: str) -> str:
        return f"episodes/{date_str}-{slug}.md"
