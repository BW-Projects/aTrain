"""End-to-end accuracy tests for the transcription pipeline.

Calculate Word Error Rate (WER) for a longer clip against a reference transcript.

Clip:
Transcript:

"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import jiwer
import pytest

WER_TRANSFORM = jiwer.Compose(
    [
        jiwer.ToLowerCase(),
        jiwer.ExpandCommonEnglishContractions(),
        jiwer.SubstituteRegexes({r"-": " "}),  # "medium-term" → "medium term"
        jiwer.RemovePunctuation(),
        jiwer.RemoveMultipleSpaces(),
        jiwer.Strip(),
        jiwer.ReduceToListOfListOfWords(),
    ]
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
WER_AUDIO = FIXTURES_DIR / "wer_lagarde.mp3"
WER_REF = FIXTURES_DIR / "reference.txt"


def _run(args, env):
    return subprocess.run(
        [sys.executable, "-m", "aTrain_core", *args],
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def atrain_env(tmp_path_factory):
    """Isolated aTrain data dir with the large-v3-turbo model preloaded."""
    data_dir = tmp_path_factory.mktemp("atrain_wer")
    env = {**os.environ, "ATRAIN_USER_DIR": str(data_dir)}
    result = _run(["load", "large-v3-turbo"], env)
    assert result.returncode == 0, f"large-v3-turbo model download failed:\n{result.stderr}"
    return env, data_dir


def _transcribe(env, data_dir, label, fixture_path, *extra_args):
    """Transcribe a uniquely named copy of the fixture; return its output dir."""
    clip = data_dir / f"{label}.mp3"
    shutil.copy(fixture_path, clip)
    transcriptions = data_dir / "transcriptions"
    before = set(transcriptions.glob("*")) if transcriptions.exists() else set()
    result = _run(
        [
            "transcribe",
            str(clip),
            "--model",
            "large-v3-turbo",
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


def test_transcription_accuracy_wer(atrain_env):
    """Calculate Word Error Rate (WER) for a longer clip."""
    env, data_dir = atrain_env
    out = _transcribe(env, data_dir, "accuracy", WER_AUDIO)

    # Drop the "Transcription for <id>" header line; the rest is the transcript.
    lines = (out / "transcription.txt").read_text().splitlines()
    hypothesis = "\n".join(lines[2:])
    reference = WER_REF.read_text()

    wer = jiwer.wer(
        reference,
        hypothesis,
        reference_transform=WER_TRANSFORM,
        hypothesis_transform=WER_TRANSFORM,
    )
    # Treshold at 5%, as large-v3-turbo resulted in 4.8% WER on real world test data. Change if too low.
    assert wer < 0.05, f"WER too high: {wer:.2%}"
