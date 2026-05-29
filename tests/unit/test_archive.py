"""Unit tests for aTrain/utils/archive.py — the transcription-archive file handler.

Characterization tests: they pin the module's CURRENT behaviour so the upcoming
aTrain_core monorepo merge can be verified not to change it. Torch- and
NiceGUI-free, so they run in the lightweight `unit` CI job (no app runtime).

archive.py binds TRANSCRIPT_DIR / METADATA_FILENAME into its own namespace via
`from aTrain_core.globals import ...`, so the filesystem tests monkeypatch
`archive.TRANSCRIPT_DIR` (the name the functions actually read), not the source
module in aTrain_core.globals.

This first PR ships a small, deliberately focused set of five tests — one per
distinct area of the module — as a baseline safety net. Broader coverage of
the remaining helpers follows in a separate PR.
"""

import pytest
from aTrain.utils import archive

_LONG = "2024-01-01 12-00-00recording.mp3"  # > 20 chars


# --- pure parsing ----------------------------------------------------------


@pytest.mark.parametrize(
    ("directory", "expected_timestamp", "expected_filename"),
    [
        pytest.param(_LONG, _LONG[:20], _LONG[20:], id="long"),
        # At exactly 20 chars the timestamp is filled (len >= 20) but the
        # filename is not (len > 20 is False) — asymmetric boundary in the
        # current code, pinned here on purpose.
        pytest.param("x" * 20, "x" * 20, "-", id="exactly-20"),
        pytest.param("short", "-", "-", id="short"),
    ],
)
def test_metadata_from_dir_name(directory, expected_timestamp, expected_filename):
    meta = archive.read_metadata_from_dir_name(directory)
    assert meta["file_id"] == directory
    assert meta["timestamp"] == expected_timestamp
    assert meta["filename"] == expected_filename


# --- filesystem listing ----------------------------------------------------


def test_read_directories_sorted_reverse_dirs_only(tmp_path, monkeypatch):
    root = tmp_path / "transcriptions"
    root.mkdir()
    for name in ("a", "b", "c"):
        (root / name).mkdir()
    (root / "loose_file.txt").write_text("x")
    monkeypatch.setattr(archive, "TRANSCRIPT_DIR", root)
    assert archive.read_directories() == ["c", "b", "a"]


# --- public orchestrator (the entry point the GUI calls) -------------------


def test_read_archive_merges_file_and_dirname_metadata(tmp_path, monkeypatch):
    # "bbb" has a metadata file, "aaa" does not. read_archive lists dirs
    # reverse-sorted (bbb before aaa) and merges both metadata sources.
    root = tmp_path / "transcriptions"
    bbb = root / "bbb"
    bbb.mkdir(parents=True)
    (bbb / archive.METADATA_FILENAME).write_text("model: tiny\n")
    (root / "aaa").mkdir(parents=True)
    monkeypatch.setattr(archive, "TRANSCRIPT_DIR", root)

    result = archive.read_archive()

    assert [m["file_id"] for m in result] == ["bbb", "aaa"]
    assert result[0]["model"] == "tiny"  # from the metadata file
    assert result[1]["filename"] == "-"  # dir-name fallback for "aaa"


# --- delete: the "all" sentinel --------------------------------------------


def test_delete_transcription_all_clears_and_recreates(tmp_path, monkeypatch):
    root = tmp_path / "transcriptions"
    (root / "rec").mkdir(parents=True)
    monkeypatch.setattr(archive, "TRANSCRIPT_DIR", root)

    archive.delete_transcription("all")

    assert root.exists()
    assert list(root.iterdir()) == []


# --- bundled resource access (importlib.resources) -------------------------


def test_load_faqs_returns_list_of_qa_entries():
    # Smoke test for importlib.resources.files("aTrain.static") resolving the
    # bundled faq.yaml — exactly the kind of resource lookup a packaging /
    # monorepo-merge change can silently break.
    # Note: load_faqs is annotated `-> dict` but the YAML is a list, so it
    # actually returns a list[dict]; pinned here as-is (the wrong annotation
    # is a separate flag, not a red test).
    faqs = archive.load_faqs()
    assert isinstance(faqs, list)
    assert all("question" in entry and "answer" in entry for entry in faqs)
