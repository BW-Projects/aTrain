"""Which events the app logs around downloads and transcriptions (#339).

No page, no worker and no model is involved, but the modules import nicegui, so
these live in tests/ui. log_event is replaced by a recorder, the dialogs and the
worker pool by stubs.
"""

from concurrent.futures.process import BrokenProcessPool
from unittest.mock import Mock

import aTrain_core.transcribe
import pytest
from aTrain.utils import models, transcription
from nicegui import app, run, ui
from nicegui.run import SubprocessException

URL = "https://huggingface.co/org/m/tree/abc"


async def _works(func, *args, **kwargs):
    return None


async def _stopped(func, *args, **kwargs):
    raise BrokenProcessPool()  # the dialog's "stop" button tears the pool down


async def _fails(func, *args, **kwargs):
    raise SubprocessException("OSError", "connection reset", "")


async def _bad_checksum(func, *args, **kwargs):
    raise SubprocessException("ModelIntegrityError", "does not match its checksums", "")


@pytest.fixture
def events(monkeypatch):
    recorded = []

    def record(event, level=None, **fields):
        recorded.append((event, fields))

    monkeypatch.setattr(models, "log_event", record)
    monkeypatch.setattr(transcription, "log_event", record)
    return recorded


@pytest.fixture
def download_stubs(monkeypatch, events):
    for name in ("dialog_download", "close_dialog_download", "dialog_error", "setup_process_pool"):
        monkeypatch.setattr(models, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(models, "remove_model", lambda *args: None)
    monkeypatch.setattr(models, "check_internet", lambda: None)
    monkeypatch.setattr(models, "model_is_complete", lambda model: False)
    monkeypatch.setattr(models, "model_url", lambda model: URL)
    monkeypatch.setattr(ui.navigate, "reload", lambda: None)


@pytest.mark.parametrize(
    ("cpu_bound", "last_event"),
    [
        pytest.param(
            _works, ("model_download_finished", {"model": "m", "checksum": "ok"}), id="ok"
        ),
        pytest.param(_stopped, ("model_download_stopped", {"model": "m"}), id="stop"),
        pytest.param(
            _fails,
            ("model_download_failed", {"model": "m", "error": "OSError: connection reset"}),
            id="error",
        ),
        pytest.param(
            _bad_checksum,
            (
                "model_download_failed",
                {
                    "model": "m",
                    "error": "ModelIntegrityError: does not match its checksums",
                    "checksum": "failed",
                },
            ),
            id="checksum",
        ),
    ],
)
async def test_download_events(download_stubs, events, monkeypatch, cpu_bound, last_event):
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)

    await models.download_model("m")

    assert events == [("model_download_started", {"model": "m", "url": URL}), last_event]


async def test_a_failed_connectivity_check_is_a_failed_download(
    download_stubs, events, monkeypatch
):
    def offline():
        raise ConnectionError("We cannot reach Hugging Face")

    monkeypatch.setattr(models, "check_internet", offline)

    await models.download_model("m")

    assert events[-1] == (
        "model_download_failed",
        {"model": "m", "error": "We cannot reach Hugging Face"},
    )


async def test_a_complete_folder_is_not_reported_as_a_download(download_stubs, events, monkeypatch):
    """get_model() returns at once for it, so no file came in and no checksum was verified."""
    monkeypatch.setattr(run, "cpu_bound", _works)
    monkeypatch.setattr(models, "model_is_complete", lambda model: True)

    await models.download_model("m")

    assert events == [("model_already_complete", {"model": "m"})]


@pytest.fixture
def pipeline_stubs(monkeypatch, events):
    for name in (
        "dialog_process",
        "close_dialog_process",
        "dialog_finished",
        "dialog_error",
        "setup_process_pool",
        "delete_transcription",
        "check_inputs_transcribe",
    ):
        monkeypatch.setattr(transcription, name, Mock())
    monkeypatch.setattr(ui.navigate, "reload", lambda: None)
    monkeypatch.setattr(transcription, "model_is_complete", lambda model: True)
    monkeypatch.setattr(transcription, "model_url", lambda model: URL)
    monkeypatch.setattr(
        aTrain_core.transcribe,
        "prepare_transcription",
        lambda file: (file, "2611051012-Intervi", "2026-11-05 10:12:00"),
    )
    # On the class, because `general` is a read-only property of the instance.
    monkeypatch.setattr(
        type(app.storage),
        "general",
        {
            "model": "m",
            "language": "de",
            "speaker_detection": False,
            "GPU": False,
            "compute_type": "int8",
            "initial_prompt": "a secret prompt",
        },
    )


@pytest.fixture
def payload(tmp_path):
    recording = tmp_path / "Interview.mp3"
    recording.write_bytes(b"12345")
    return transcription.UploadPayload(name="Interview.mp3", path=recording)


ACCEPTED = ("file_accepted", {"file": "Interview.mp3", "size": 5})
STARTED = (
    "transcription_started",
    {"file_id": "2611051012-Intervi", "model": "m", "device": "cpu"},
)


@pytest.mark.parametrize(
    ("cpu_bound", "last_event"),
    [
        pytest.param(
            _works, ("transcription_finished", {"file_id": "2611051012-Intervi"}), id="ok"
        ),
        pytest.param(
            _stopped, ("transcription_stopped", {"file_id": "2611051012-Intervi"}), id="stop"
        ),
        pytest.param(
            _fails,
            (
                "transcription_failed",
                {"file_id": "2611051012-Intervi", "error": "OSError: connection reset"},
            ),
            id="error",
        ),
    ],
)
async def test_transcription_events(
    pipeline_stubs, payload, events, monkeypatch, cpu_bound, last_event
):
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)

    await transcription.run_pipeline(payload)

    assert events == [ACCEPTED, STARTED, last_event]


async def test_a_rejected_file_is_logged_and_not_transcribed(
    pipeline_stubs, payload, events, monkeypatch
):
    cpu_bound = Mock(side_effect=_works)
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)
    monkeypatch.setattr(
        transcription, "check_inputs_transcribe", Mock(side_effect=ValueError("Incorrect input."))
    )

    await transcription.run_pipeline(payload)

    assert events[-1] == (
        "file_rejected",
        {"file": "Interview.mp3", "size": 5, "reason": "Incorrect input."},
    )
    cpu_bound.assert_not_called()


async def test_a_download_inside_the_worker_is_announced(
    pipeline_stubs, payload, events, monkeypatch
):
    """get_model() in the worker fetches a missing model without telling the server."""
    monkeypatch.setattr(run, "cpu_bound", _works)
    app.storage.general["speaker_detection"] = True
    monkeypatch.setattr(
        transcription, "model_is_complete", lambda model: model != "speaker-detection"
    )

    await transcription.run_pipeline(payload)

    assert events[1] == (
        "model_download_by_transcription",
        {"model": "speaker-detection", "url": URL},
    )


async def test_the_initial_prompt_stays_out_of_the_log(
    pipeline_stubs, payload, events, monkeypatch
):
    monkeypatch.setattr(run, "cpu_bound", _works)

    await transcription.run_pipeline(payload)

    assert "a secret prompt" not in str(events)
