"""Build and verify the StudyPilot finals desktop and submission packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWLIST = Path("final-competition/package-allowlist.json")
MANIFEST_NAME = "final-package-manifest.json"
HASHES_NAME = "SHA256SUMS.txt"
SCHEMA = "studypilot-finals-package-v1"

FORBIDDEN_COMPONENTS = {
    ".git",
    ".hypothesis",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".superpowers",
    ".venv",
    ".worktrees",
    "__pycache__",
    "dist",
    "node_modules",
    "pilot",
    "private",
    "test-results",
}
FORBIDDEN_PREFIXES = {
    ("data", "local"),
    ("evaluation", "results"),
}
# The desktop bundle may have locally installed runtime dependencies.  They are
# deliberately ignored by the verifier and never participate in the manifest.
DESKTOP_RUNTIME_COMPONENTS = {
    ".hypothesis",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "test-results",
}
DESKTOP_RUNTIME_SUFFIXES = (".coverage", ".tsbuildinfo")
FORBIDDEN_SUFFIXES = (
    ".db",
    ".db-journal",
    ".db-shm",
    ".db-wal",
    ".db3",
    ".log",
    ".pid",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".tsbuildinfo",
)
_WINDOWS_RESERVED = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class FinalPackageError(RuntimeError):
    """Raised when a finals package cannot be built safely."""


class PackageVerificationError(RuntimeError):
    """Raised when a built finals package does not match its manifest."""


@dataclass(frozen=True)
class PackageFile:
    source: str
    desktop: str
    submission: str
    role: str
    visibility: str
    sha256: str
    size: int


@dataclass(frozen=True)
class PackageVerificationResult:
    package_root: Path
    package_kind: str
    file_count: int
    common_source_digest: str


@dataclass(frozen=True)
class FinalBuildResult:
    desktop_root: Path
    submission_root: Path
    file_count: int
    common_source_digest: str


def _utc_build_time() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_error(value: str) -> str | None:
    if not value or "\\" in value:
        return "path is empty or uses a backslash"
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).is_absolute() or value != path.as_posix():
        return "path is not a normalized relative POSIX path"
    if any(part in {"", ".", ".."} for part in path.parts):
        return "path contains traversal"
    for part in path.parts:
        if any(ord(character) < 32 for character in part):
            return "path contains a control character"
        if any(character in '<>:"|?*' for character in part):
            return "path is not portable to Windows"
        if part.endswith((" ", ".")):
            return "path has a trailing space or dot"
        if part.split(".", 1)[0].casefold() in _WINDOWS_RESERVED:
            return "path uses a reserved Windows device name"
    return None


def _forbidden_reason(value: str) -> str | None:
    shape_error = _path_error(value)
    if shape_error is not None:
        return shape_error
    parts = tuple(part.casefold() for part in PurePosixPath(value).parts)
    prefix = next(
        (
            blocked
            for blocked in FORBIDDEN_PREFIXES
            if any(
                parts[index : index + len(blocked)] == blocked
                for index in range(len(parts) - len(blocked) + 1)
            )
        ),
        None,
    )
    if prefix is not None:
        return f"forbidden path prefix: {'/'.join(prefix)}"
    component = next((part for part in parts if part in FORBIDDEN_COMPONENTS), None)
    if component is not None:
        return f"forbidden path component: {component}"
    if any(part.endswith(".egg-info") for part in parts):
        return "generated package metadata"
    filename = parts[-1]
    if filename == ".env" or filename.startswith(".env.") and filename != ".env.example":
        return "private environment file"
    if filename.endswith(FORBIDDEN_SUFFIXES):
        return "forbidden generated or private suffix"
    return None


def _load_allowlist(source_root: Path, allowlist_path: Path | None) -> dict[str, Any]:
    path = allowlist_path or source_root / DEFAULT_ALLOWLIST
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FinalPackageError(f"cannot read package allowlist: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise FinalPackageError("package allowlist must use schema_version 1")
    for key in ("directory_rules", "file_rules"):
        if not isinstance(payload.get(key), list):
            raise FinalPackageError(f"package allowlist field must be a list: {key}")
    return payload


def _safe_source(source_root: Path, relative_path: str, *, expect_dir: bool) -> Path:
    reason = _path_error(relative_path)
    if reason is not None:
        raise FinalPackageError(f"unsafe source path {relative_path}: {reason}")
    candidate = source_root.joinpath(*PurePosixPath(relative_path).parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(source_root)
    except (OSError, ValueError) as exc:
        raise FinalPackageError(f"source path is missing or escapes source root: {relative_path}") from exc
    current = candidate
    while current != source_root:
        if current.is_symlink() or bool(getattr(current, "is_junction", lambda: False)()):
            raise FinalPackageError(f"source path crosses a link or junction: {relative_path}")
        current = current.parent
    if expect_dir and not candidate.is_dir():
        raise FinalPackageError(f"source directory is missing: {relative_path}")
    if not expect_dir and not candidate.is_file():
        raise FinalPackageError(f"source file is missing: {relative_path}")
    return candidate


def _rule_text(rule: dict[str, Any], key: str) -> str:
    value = rule.get(key)
    if not isinstance(value, str) or not value:
        raise FinalPackageError(f"allowlist rule requires a non-empty string: {key}")
    return value


def _package_file(
    source_root: Path,
    source_path: str,
    desktop_path: str,
    submission_path: str,
    role: str,
    visibility: str,
) -> PackageFile:
    source_reason = _forbidden_reason(source_path)
    if source_reason is not None:
        raise FinalPackageError(
            f"forbidden source {source_path}: {source_reason}"
        )
    source = _safe_source(source_root, source_path, expect_dir=False)
    for target in (desktop_path, submission_path):
        reason = _forbidden_reason(target)
        if reason is not None:
            raise FinalPackageError(f"unsafe package target {target}: {reason}")
    return PackageFile(
        source=source_path,
        desktop=desktop_path,
        submission=submission_path,
        role=role,
        visibility=visibility,
        sha256=_sha256(source),
        size=source.stat().st_size,
    )


def _expand_allowlist(source_root: Path, payload: dict[str, Any]) -> list[PackageFile]:
    files: list[PackageFile] = []
    for raw_rule in payload["directory_rules"]:
        if not isinstance(raw_rule, dict):
            raise FinalPackageError("directory allowlist entry must be an object")
        source_base = _rule_text(raw_rule, "source")
        source_reason = _forbidden_reason(source_base)
        if source_reason is not None:
            raise FinalPackageError(
                f"forbidden source directory {source_base}: {source_reason}"
            )
        desktop_base = _rule_text(raw_rule, "desktop")
        submission_base = _rule_text(raw_rule, "submission")
        role = _rule_text(raw_rule, "role")
        visibility = _rule_text(raw_rule, "visibility")
        raw_suffixes = raw_rule.get("suffixes")
        if not isinstance(raw_suffixes, list) or not raw_suffixes:
            raise FinalPackageError(f"directory rule requires suffixes: {source_base}")
        suffixes = {
            value.casefold()
            for value in raw_suffixes
            if isinstance(value, str) and value.startswith(".")
        }
        if len(suffixes) != len(raw_suffixes):
            raise FinalPackageError(f"directory rule has invalid suffixes: {source_base}")
        source_directory = _safe_source(source_root, source_base, expect_dir=True)
        matched = 0
        for path in sorted(source_directory.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source_root).as_posix()
            if _forbidden_reason(relative) is not None:
                continue
            if path.suffix.casefold() not in suffixes:
                continue
            nested = path.relative_to(source_directory).as_posix()
            files.append(
                _package_file(
                    source_root,
                    relative,
                    f"{desktop_base}/{nested}",
                    f"{submission_base}/{nested}",
                    role,
                    visibility,
                )
            )
            matched += 1
        if matched == 0:
            raise FinalPackageError(f"directory rule selected no files: {source_base}")

    for raw_rule in payload["file_rules"]:
        if not isinstance(raw_rule, dict):
            raise FinalPackageError("file allowlist entry must be an object")
        files.append(
            _package_file(
                source_root,
                _rule_text(raw_rule, "source"),
                _rule_text(raw_rule, "desktop"),
                _rule_text(raw_rule, "submission"),
                _rule_text(raw_rule, "role"),
                _rule_text(raw_rule, "visibility"),
            )
        )

    if not files:
        raise FinalPackageError("package allowlist selected no files")
    source_keys: dict[str, str] = {}
    target_keys: dict[str, dict[str, str]] = {"desktop": {}, "submission": {}}
    for entry in files:
        source_key = unicodedata.normalize("NFC", entry.source).casefold()
        if source_key in source_keys:
            raise FinalPackageError(f"duplicate package source: {entry.source}")
        source_keys[source_key] = entry.source
        for kind in target_keys:
            target = getattr(entry, kind)
            key = unicodedata.normalize("NFC", target).casefold()
            if key in target_keys[kind]:
                raise FinalPackageError(
                    f"duplicate {kind} target: {target_keys[kind][key]}, {target}"
                )
            target_keys[kind][key] = target
    return sorted(files, key=lambda entry: entry.source)


def _common_source_digest(files: list[PackageFile]) -> str:
    lines = "".join(f"{entry.sha256}  {entry.source}\n" for entry in files)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def _metadata_paths(kind: str) -> tuple[str, str]:
    if kind == "desktop":
        return f"04_启动说明/{MANIFEST_NAME}", f"04_启动说明/{HASHES_NAME}"
    if kind == "submission":
        return MANIFEST_NAME, HASHES_NAME
    raise FinalPackageError(f"unknown package kind: {kind}")


def _write_package(
    source_root: Path,
    stage: Path,
    files: list[PackageFile],
    kind: str,
    build_time_utc: str,
    common_digest: str,
) -> None:
    for entry in files:
        target = getattr(entry, kind)
        destination = stage.joinpath(*PurePosixPath(target).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root.joinpath(*PurePosixPath(entry.source).parts), destination)

    manifest_relative, hashes_relative = _metadata_paths(kind)
    manifest_path = stage.joinpath(*PurePosixPath(manifest_relative).parts)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": SCHEMA,
        "package_kind": kind,
        "build_time_utc": build_time_utc,
        "common_source_digest": common_digest,
        "file_count": len(files),
        "files": [
            {
                "source": entry.source,
                "target": getattr(entry, kind),
                "role": entry.role,
                "visibility": entry.visibility,
                "size": entry.size,
                "sha256": entry.sha256,
            }
            for entry in files
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    hash_paths = sorted([getattr(entry, kind) for entry in files] + [manifest_relative])
    hashes_path = stage.joinpath(*PurePosixPath(hashes_relative).parts)
    hashes_path.write_text(
        "".join(
            f"{_sha256(stage.joinpath(*PurePosixPath(path).parts))}  {path}\n"
            for path in hash_paths
        ),
        encoding="utf-8",
        newline="\n",
    )


def _walk_files(root: Path, *, allow_desktop_runtime: bool = False) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in directory_names:
            child = base / name
            if child.is_symlink() or bool(getattr(child, "is_junction", lambda: False)()):
                raise PackageVerificationError(f"package contains a link or junction: {child}")
        if allow_desktop_runtime:
            directory_names[:] = [
                name
                for name in directory_names
                if (
                    name.casefold() not in DESKTOP_RUNTIME_COMPONENTS
                    and not name.casefold().endswith(".egg-info")
                    and not (
                        base.name.casefold() == "data"
                        and name.casefold() == "local"
                    )
                )
            ]
        for name in file_names:
            child = base / name
            if child.is_symlink():
                raise PackageVerificationError(f"package contains a symlink: {child}")
            relative = child.relative_to(root).as_posix()
            if allow_desktop_runtime and relative.casefold().endswith(DESKTOP_RUNTIME_SUFFIXES):
                continue
            reason = _forbidden_reason(relative)
            if reason is not None:
                raise PackageVerificationError(f"package contains forbidden file {relative}: {reason}")
            files[relative] = child
    return files


def _load_hashes(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text("utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise PackageVerificationError(f"cannot read hashes: {path}") from exc
    result: dict[str, str] = {}
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            raise PackageVerificationError("invalid SHA256SUMS entry")
        digest, relative = line[:64], line[66:]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise PackageVerificationError("invalid SHA256SUMS digest")
        path_error = _path_error(relative)
        if path_error is not None:
            raise PackageVerificationError(
                f"invalid SHA256SUMS path {relative}: {path_error}"
            )
        if relative in result:
            raise PackageVerificationError(f"duplicate SHA256SUMS path: {relative}")
        result[relative] = digest
    return result


def verify_final_package(
    package_root: str | Path,
    *,
    expected_kind: str,
) -> PackageVerificationResult:
    root = Path(package_root).resolve()
    if not root.is_dir():
        raise PackageVerificationError(f"package root is missing: {root}")
    manifest_relative, hashes_relative = _metadata_paths(expected_kind)
    files = _walk_files(root, allow_desktop_runtime=expected_kind == "desktop")
    try:
        manifest = json.loads(files[manifest_relative].read_text("utf-8"))
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageVerificationError("package manifest is missing or invalid") from exc
    if manifest.get("schema") != SCHEMA or manifest.get("package_kind") != expected_kind:
        raise PackageVerificationError("package manifest schema or kind is invalid")
    entries = manifest.get("files")
    if not isinstance(entries, list) or manifest.get("file_count") != len(entries):
        raise PackageVerificationError("package manifest file count is invalid")
    targets: dict[str, dict[str, Any]] = {}
    target_keys: dict[str, str] = {}
    source_keys: dict[str, str] = {}
    source_lines: list[str] = []
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise PackageVerificationError("package manifest file entry is invalid")
        target = raw_entry.get("target")
        source = raw_entry.get("source")
        digest = raw_entry.get("sha256")
        size = raw_entry.get("size")
        if not isinstance(target, str) or not isinstance(source, str) or not isinstance(digest, str):
            raise PackageVerificationError("package manifest file fields are invalid")
        source_error = _forbidden_reason(source)
        if source_error is not None:
            raise PackageVerificationError(
                f"manifest contains forbidden source {source}: {source_error}"
            )
        source_key = unicodedata.normalize("NFC", source).casefold()
        if source_key in source_keys:
            raise PackageVerificationError(
                f"duplicate manifest source: {source_keys[source_key]}, {source}"
            )
        source_keys[source_key] = source
        target_key = unicodedata.normalize("NFC", target).casefold()
        if target_key in target_keys:
            raise PackageVerificationError(
                f"duplicate manifest target: {target_keys[target_key]}, {target}"
            )
        target_keys[target_key] = target
        reason = _forbidden_reason(target)
        if reason is not None:
            raise PackageVerificationError(f"manifest contains forbidden target {target}: {reason}")
        payload = files.get(target)
        if payload is None:
            raise PackageVerificationError(f"manifest payload is missing: {target}")
        if _sha256(payload) != digest:
            raise PackageVerificationError(f"hash mismatch: {target}")
        if not isinstance(size, int) or payload.stat().st_size != size:
            raise PackageVerificationError(f"size mismatch: {target}")
        targets[target] = raw_entry
        source_lines.append(f"{digest}  {source}\n")
    source_lines.sort(key=lambda line: line.split("  ", 1)[1])
    common_digest = hashlib.sha256("".join(source_lines).encode("utf-8")).hexdigest()
    if manifest.get("common_source_digest") != common_digest:
        raise PackageVerificationError("common source digest mismatch")

    expected_files = set(targets) | {manifest_relative, hashes_relative}
    if set(files) != expected_files:
        extras = sorted(set(files) - expected_files)
        missing = sorted(expected_files - set(files))
        raise PackageVerificationError(f"package file set mismatch: extras={extras}, missing={missing}")
    hashes = _load_hashes(files[hashes_relative])
    expected_hash_paths = set(targets) | {manifest_relative}
    if set(hashes) != expected_hash_paths:
        raise PackageVerificationError("SHA256SUMS file set mismatch")
    for relative, digest in hashes.items():
        payload = files.get(relative)
        if payload is None:
            raise PackageVerificationError(f"SHA256SUMS payload is missing: {relative}")
        if _sha256(payload) != digest:
            raise PackageVerificationError(f"SHA256SUMS hash mismatch: {relative}")
    return PackageVerificationResult(
        package_root=root,
        package_kind=expected_kind,
        file_count=len(entries),
        common_source_digest=common_digest,
    )


def build_final_packages(
    source_root: str | Path,
    desktop_output: str | Path,
    submission_output: str | Path,
    *,
    allowlist_path: str | Path | None = None,
    build_time_utc: str | None = None,
) -> FinalBuildResult:
    source = Path(source_root).resolve()
    if not source.is_dir():
        raise FinalPackageError(f"source root is missing: {source}")
    desktop = Path(desktop_output).resolve()
    submission = Path(submission_output).resolve()
    if desktop == submission:
        raise FinalPackageError("desktop and submission outputs must differ")
    for output in (desktop, submission):
        if os.path.lexists(output):
            raise FinalPackageError(f"formal output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)

    allowlist = _load_allowlist(
        source,
        Path(allowlist_path).resolve() if allowlist_path is not None else None,
    )
    files = _expand_allowlist(source, allowlist)
    common_digest = _common_source_digest(files)
    build_time = build_time_utc or _utc_build_time()
    desktop_stage = desktop.parent / f".{desktop.name}.staging-{uuid.uuid4().hex}"
    submission_stage = submission.parent / f".{submission.name}.staging-{uuid.uuid4().hex}"
    published: list[Path] = []
    try:
        desktop_stage.mkdir()
        submission_stage.mkdir()
        _write_package(source, desktop_stage, files, "desktop", build_time, common_digest)
        _write_package(source, submission_stage, files, "submission", build_time, common_digest)
        verify_final_package(desktop_stage, expected_kind="desktop")
        verify_final_package(submission_stage, expected_kind="submission")
        desktop_stage.replace(desktop)
        published.append(desktop)
        submission_stage.replace(submission)
        published.append(submission)
        verify_final_package(desktop, expected_kind="desktop")
        verify_final_package(submission, expected_kind="submission")
    except (OSError, PackageVerificationError) as exc:
        for path in published:
            if path.is_dir():
                shutil.rmtree(path)
        raise FinalPackageError(f"final package build failed: {exc}") from exc
    finally:
        for stage in (desktop_stage, submission_stage):
            if stage.is_dir():
                shutil.rmtree(stage)
    return FinalBuildResult(
        desktop_root=desktop,
        submission_root=submission,
        file_count=len(files),
        common_source_digest=common_digest,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT)
    build_parser.add_argument("--desktop-output", type=Path, required=True)
    build_parser.add_argument("--submission-output", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--package", type=Path, required=True)
    verify_parser.add_argument("--kind", choices=("desktop", "submission"), required=True)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "build":
            result = build_final_packages(
                arguments.source_root,
                arguments.desktop_output,
                arguments.submission_output,
            )
            print(
                json.dumps(
                    {
                        "common_source_digest": result.common_source_digest,
                        "desktop_root": str(result.desktop_root),
                        "file_count": result.file_count,
                        "submission_root": str(result.submission_root),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            result = verify_final_package(arguments.package, expected_kind=arguments.kind)
            print(
                json.dumps(
                    {
                        "common_source_digest": result.common_source_digest,
                        "file_count": result.file_count,
                        "package_kind": result.package_kind,
                        "package_root": str(result.package_root),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    except (FinalPackageError, PackageVerificationError) as exc:
        print(f"final package error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
