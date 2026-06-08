"""Tests for ``LocalArtifactStorage``."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.storage.artifact_store import (
    LocalArtifactStorage,
    MissionArtifact,
)


@pytest.fixture(name="storage")
def fixture_storage(tmp_path: Path) -> LocalArtifactStorage:
  return LocalArtifactStorage(
      base_dir=tmp_path,
      public_base="http://test.local/mock_data",
  )


def test_persist_writes_file_and_returns_namespaced_name(
    storage: LocalArtifactStorage, tmp_path: Path
) -> None:
  artifact = MissionArtifact(
      filename="user_activities.csv",
      mime_type="text/csv",
      content="a,b\n1,2\n",
  )
  stored = storage.persist("mvp_mission_data_1", artifact)

  assert stored.startswith("mvp_mission_data_1__")
  assert stored.endswith(".csv")
  assert (tmp_path / stored).read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_persist_strips_path_separators_and_unsafe_chars(
    storage: LocalArtifactStorage, tmp_path: Path
) -> None:
  artifact = MissionArtifact(
      filename="../../../etc/passwd evil name.csv",
      mime_type="text/csv",
      content="x,y\n",
  )
  stored = storage.persist("mvp_mission_data_1", artifact)
  # No path separators leak into the stored name.
  assert "/" not in stored and "\\" not in stored
  assert ".." not in stored
  assert (tmp_path / stored).is_file()


def test_persist_forces_extension_to_match_mime(
    storage: LocalArtifactStorage,
) -> None:
  artifact = MissionArtifact(
      filename="weird_name.txt",
      mime_type="text/csv",
      content="ok\n",
  )
  stored = storage.persist("mvp_mission_data_1", artifact)
  assert stored.endswith(".csv")


def test_persist_rejects_unsupported_mime(storage: LocalArtifactStorage) -> None:
  artifact = MissionArtifact(
      filename="x.bin",
      mime_type="application/octet-stream",
      content="ignored",
  )
  with pytest.raises(ValueError):
    storage.persist("mvp_mission_data_1", artifact)


def test_copy_sample_copies_with_namespaced_name(
    storage: LocalArtifactStorage, tmp_path: Path
) -> None:
  src = tmp_path / "source.csv"
  src.write_text("h\n1\n", encoding="utf-8")
  stored = storage.copy_sample("mvp_mission_data_1", src)
  assert stored.startswith("mvp_mission_data_1__")
  assert stored.endswith(".csv")
  # Source must not be the same file as target.
  assert (tmp_path / stored).read_text(encoding="utf-8") == "h\n1\n"


def test_copy_sample_missing_source_raises(
    storage: LocalArtifactStorage, tmp_path: Path
) -> None:
  with pytest.raises(FileNotFoundError):
    storage.copy_sample("m1", tmp_path / "missing.csv")


def test_read_text_returns_truncated_content(
    storage: LocalArtifactStorage,
) -> None:
  artifact = MissionArtifact(
      filename="big.csv",
      mime_type="text/csv",
      content="x" * 5000,
  )
  stored = storage.persist("m1", artifact)
  excerpt = storage.read_text(stored, max_bytes=100)
  assert len(excerpt) == 100
  assert excerpt == "x" * 100


def test_read_text_missing_file_raises(storage: LocalArtifactStorage) -> None:
  with pytest.raises(FileNotFoundError):
    storage.read_text("does_not_exist.csv")


def test_build_url_uses_public_base(storage: LocalArtifactStorage) -> None:
  assert storage.build_url("foo.csv") == "http://test.local/mock_data/foo.csv"


def test_persist_idempotent_overwrites_same_name(
    storage: LocalArtifactStorage, tmp_path: Path
) -> None:
  a1 = MissionArtifact(filename="d.csv", mime_type="text/csv", content="v1\n")
  a2 = MissionArtifact(filename="d.csv", mime_type="text/csv", content="v2\n")
  s1 = storage.persist("m1", a1)
  s2 = storage.persist("m1", a2)
  assert s1 == s2
  assert (tmp_path / s2).read_text(encoding="utf-8") == "v2\n"
