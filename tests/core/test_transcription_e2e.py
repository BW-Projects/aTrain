"""End-to-end smoke tests for the transcription pipeline.

Drive the real engine (audio decode -> CTranslate2 inference -> output file
generation) on a short clip with the tiny model on CPU, with speaker
detection both off and on. These are smoke tests, not accuracy tests (WER is
tracked separately in #147).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_short.mp3"


def _run(args, env):
    return subprocess.run(
        [sys.executable, "-m", "aTrain_core", *args],
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def atrain_env(tmp_path_factory):
    """Isolated aTrain data dir with the tiny model preloaded."""
    data_dir = tmp_path_factory.mktemp("atrain")
    env = {**os.environ, "ATRAIN_USER_DIR": str(data_dir)}
    result = _run(["load", "tiny"], env)
    assert result.returncode == 0, f"tiny model download failed:\n{result.stderr}"
    return env, data_dir


def _transcribe(env, data_dir, label, *extra_args):
    """Transcribe a uniquely named copy of the fixture; return its output dir.

    The output dir name (file_id) is `timestamp + filename` at minute
    precision, so two runs of the same filename within a minute would collide.
    A per-test filename keeps them distinct while sharing the model cache.
    """
    clip = data_dir / f"{label}.mp3"
    shutil.copy(FIXTURE, clip)
    transcriptions = data_dir / "transcriptions"
    before = set(transcriptions.glob("*")) if transcriptions.exists() else set()
    result = _run(
        [
            "transcribe",
            str(clip),
            "--model",
            "tiny",
            "--device",
            "cpu",
            "--language",
            "auto-detect",
            *extra_args,
        ],
        env,
    )
    assert result.returncode == 0, f"transcription failed:\n{result.stderr}"
    new = [d for d in set(transcriptions.glob("*")) - before if d.is_dir()]
    assert len(new) == 1, f"expected exactly one new output dir, got {new}"
    return new[0]


def test_transcribe_short_clip(atrain_env):
    env, data_dir = atrain_env
    out = _transcribe(env, data_dir, "plain")
    for name in ("transcription.txt", "transcription.srt", "transcription.json"):
        assert (out / name).is_file(), f"missing output file: {name}"
    # Drop the "Transcription for <id>" header line; the rest is the transcript.
    body = "\n".join((out / "transcription.txt").read_text().splitlines()[2:])
    assert len(body.split()) >= 3, f"transcript body unexpectedly short: {body!r}"


def test_transcribe_with_speaker_detection(atrain_env):
    env, data_dir = atrain_env
    out = _transcribe(env, data_dir, "diarized", "--speaker-detection")
    text = (out / "transcription.txt").read_text()
    # Smoke check that the diarization path ran and labelled a speaker — not an
    # exact speaker count, which is brittle on a short clip (accuracy territory).
    assert "SPEAKER_" in text, f"no speaker label in diarized output:\n{text}"
