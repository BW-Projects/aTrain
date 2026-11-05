"""Which events the app logs around downloads, transcriptions and `aTrain start` (#339).

No page, no worker and no model is involved, but the modules import nicegui, so
these live in tests/ui. log_event is replaced by a recorder, the dialogs and the
worker pool by stubs.
"""

import asyncio
import contextlib
import sys
from concurrent.futures.process import BrokenProcessPool
from unittest.mock import Mock

import aTrain.app as atrain_cli
import aTrain_core.transcribe
import pytest
from aTrain.utils import models, transcription
from aTrain.version import __version__
from aTrain_core.integrity import ModelIntegrityError
from nicegui import app, run, ui
from nicegui.run import SubprocessException
from wakepy import keep

URL = "https://huggingface.co/org/m/tree/abc"


async def _works(func, *args, **kwargs):
    return "done"


async def _stopped(func, *args, **kwargs):
    raise BrokenProcessPool()  # the dialog's "stop" button tears the pool down


async def _not_run(func, *args, **kwargs):
    return None  # NiceGUI 3 after a stop while no worker ran, or at server shutdown


async def _cancelled(func, *args, **kwargs):
    raise asyncio.CancelledError()  # NiceGUI 4 in the same cases


async def _fails(func, *args, **kwargs):
    raise SubprocessException("OSError", "connection reset", "")


async def _bad_checksum(func, *args, **kwargs):
    raise SubprocessException("ModelIntegrityError", "does not match its checksums", "")


def _recorder(recorded):
    def record(event, level=None, **fields):
        recorded.append((event, fields))

    return record


@pytest.fixture
def events(monkeypatch):
    recorded = []
    monkeypatch.setattr(models, "log_event", _recorder(recorded))
    monkeypatch.setattr(transcription, "log_event", _recorder(recorded))
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


STOPPED_DOWNLOAD = ("model_download_stopped", {"model": "m"})


@pytest.mark.parametrize(
    ("cpu_bound", "last_event"),
    [
        pytest.param(
            _works, ("model_download_finished", {"model": "m", "checksum": "ok"}), id="ok"
        ),
        pytest.param(_stopped, STOPPED_DOWNLOAD, id="stop"),
        pytest.param(_not_run, STOPPED_DOWNLOAD, id="not run"),
        pytest.param(_cancelled, STOPPED_DOWNLOAD, id="cancelled"),
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
    """get_model() returns at once for a complete folder.

    Nothing is downloaded and no checksum is verified.
    """
    monkeypatch.setattr(run, "cpu_bound", _works)
    monkeypatch.setattr(models, "model_is_complete", lambda model: True)

    await models.download_model("m")

    assert events == []


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


ACCEPTED = ("file_accepted", {"file_name": "Interview.mp3", "size": 5})
STARTED = (
    "transcription_started",
    {"file_id": "2611051012-Intervi", "model": "m", "device": "cpu"},
)
FINISHED = ("transcription_finished", {"file_id": "2611051012-Intervi"})
STOPPED = ("transcription_stopped", {"file_id": "2611051012-Intervi"})


@pytest.mark.parametrize(
    ("cpu_bound", "last_event"),
    [
        pytest.param(_works, FINISHED, id="ok"),
        pytest.param(_stopped, STOPPED, id="stop"),
        pytest.param(_not_run, STOPPED, id="not run"),
        pytest.param(_cancelled, STOPPED, id="cancelled"),
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


@pytest.mark.parametrize("cpu_bound", [_not_run, _cancelled], ids=["not run", "cancelled"])
async def test_a_transcription_that_never_ran_ends_like_a_stop(
    pipeline_stubs, payload, monkeypatch, cpu_bound
):
    """Stop pressed while the upload is still being copied.

    No worker runs yet, so there is no BrokenProcessPool, only a pool that is shut down.
    """
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)

    await transcription.run_pipeline(payload)

    transcription.dialog_finished.assert_not_called()
    transcription.delete_transcription.assert_called_once_with("2611051012-Intervi")
    transcription.setup_process_pool.assert_called_once()


async def test_a_rejected_file_is_logged_and_not_transcribed(
    pipeline_stubs, payload, events, monkeypatch
):
    cpu_bound = Mock(side_effect=_works)
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)
    monkeypatch.setattr(
        transcription, "check_inputs_transcribe", Mock(side_effect=ValueError("Incorrect input."))
    )

    await transcription.run_pipeline(payload)

    assert events == [
        ("file_rejected", {"file_name": "Interview.mp3", "size": 5, "reason": "Incorrect input."})
    ]
    cpu_bound.assert_not_called()


async def test_a_file_that_is_gone_is_still_rejected_with_its_reason(
    pipeline_stubs, payload, events, monkeypatch
):
    payload.path.unlink()
    monkeypatch.setattr(
        transcription, "check_inputs_transcribe", Mock(side_effect=ValueError("Incorrect input."))
    )

    await transcription.run_pipeline(payload)

    assert events == [
        (
            "file_rejected",
            {"file_name": "Interview.mp3", "size": None, "reason": "Incorrect input."},
        )
    ]
    assert transcription.dialog_error.call_args.kwargs["error"] == "Incorrect input."


async def test_a_failure_before_the_worker_starts_is_logged(
    pipeline_stubs, payload, events, monkeypatch
):
    def read_only(file):
        raise PermissionError("the transcriptions folder is read-only")

    monkeypatch.setattr(aTrain_core.transcribe, "prepare_transcription", read_only)

    await transcription.run_pipeline(payload)

    assert events == [
        ACCEPTED,
        (
            "transcription_failed",
            {"file_id": None, "error": "the transcriptions folder is read-only"},
        ),
    ]


@pytest.fixture
def speaker_detection(pipeline_stubs, monkeypatch):
    """Speaker detection is on and its model is missing until the worker fetched it."""
    app.storage.general["speaker_detection"] = True
    on_disk = {"m"}
    monkeypatch.setattr(transcription, "model_is_complete", lambda model: model in on_disk)
    return on_disk


async def test_a_download_inside_the_worker_is_announced_and_finished(
    speaker_detection, payload, events, monkeypatch
):
    """get_model() in the worker fetches a missing model without telling the server."""

    async def fetches(func, *args, **kwargs):
        speaker_detection.add("speaker-detection")
        return "done"

    monkeypatch.setattr(run, "cpu_bound", fetches)

    await transcription.run_pipeline(payload)

    assert events == [
        ACCEPTED,
        ("model_download_by_transcription", {"model": "speaker-detection", "url": URL}),
        STARTED,
        ("model_download_finished", {"model": "speaker-detection", "checksum": "ok"}),
        FINISHED,
    ]


async def test_a_model_the_worker_did_not_fetch_is_not_reported_finished(
    speaker_detection, payload, events, monkeypatch
):
    """With an empty transcript the worker skips speaker detection and never loads its model."""
    monkeypatch.setattr(run, "cpu_bound", _works)

    await transcription.run_pipeline(payload)

    assert events[-1] == FINISHED
    assert "model_download_finished" not in [event for event, _ in events]


async def test_the_initial_prompt_stays_out_of_the_log(
    pipeline_stubs, payload, events, monkeypatch
):
    monkeypatch.setattr(run, "cpu_bound", _works)

    await transcription.run_pipeline(payload)

    assert "a secret prompt" not in str(events)


@pytest.fixture
def cli_events(monkeypatch):
    """`aTrain start` and `aTrain init` without a log file, a server or a wake lock."""
    recorded = []
    monkeypatch.setattr(atrain_cli, "setup_event_log", lambda: None)
    monkeypatch.setattr(atrain_cli, "log_event", _recorder(recorded))
    monkeypatch.setattr(
        atrain_cli,
        "log_unhandled_exception",
        lambda error: recorded.append(("unhandled_exception", {"error": str(error)})),
    )
    # The host check adds a middleware to the global app. The stub keeps it out of
    # the other tests.
    monkeypatch.setattr(atrain_cli, "restrict_to_loopback_hosts", Mock())
    monkeypatch.setattr(app, "on_shutdown", Mock())
    monkeypatch.setattr(app, "on_exception", Mock())
    monkeypatch.setattr(ui, "run", Mock())
    monkeypatch.setattr(keep, "running", contextlib.nullcontext)
    # start() sets the pool's start method; keep that from leaking into other tests.
    monkeypatch.setattr(run, "process_pool_start_method", run.process_pool_start_method)
    # start() imports the page modules. If they stayed in sys.modules, the user tests
    # that follow would reuse them and their routes would be missing (see
    # tests/ui/main.py).
    monkeypatch.setitem(sys.modules, "aTrain.pages", Mock())
    return recorded


def _start(**options):
    defaults = {"native": False, "reload": False, "show": False, "host": None, "port": 8100}
    atrain_cli.start(**{**defaults, **options})


def test_start_logs_the_server_and_registers_the_hooks(cli_events):
    _start()

    assert cli_events == [
        (
            "server_started",
            {
                "version": __version__,
                "native": False,
                "host": "127.0.0.1",
                "port": 8100,
                "allow_any_host": False,
            },
        )
    ]
    app.on_exception.assert_called_once_with(atrain_cli.log_unhandled_exception)
    on_stop = app.on_shutdown.call_args.args[0]
    on_stop()
    assert cli_events[-1] == ("server_stopped", {})


def test_start_logs_a_switched_off_host_check(cli_events):
    _start(host="localhost", allow_any_host=True)

    assert cli_events[0][1]["host"] == "localhost"
    assert cli_events[0][1]["allow_any_host"] is True
    atrain_cli.restrict_to_loopback_hosts.assert_not_called()


def test_a_crash_at_startup_is_logged(cli_events, monkeypatch):
    """The Windows build has no console, so the log is the only trace of it."""
    monkeypatch.setattr(ui, "run", Mock(side_effect=RuntimeError("cannot bind")))

    with pytest.raises(RuntimeError):
        _start()

    assert cli_events[-1] == ("unhandled_exception", {"error": "cannot bind"})


@pytest.fixture
def init_stubs(cli_events, monkeypatch):
    monkeypatch.setattr(atrain_cli, "REQUIRED_MODELS", ["m", "on-disk"])
    monkeypatch.setattr(atrain_cli, "model_is_complete", lambda model: model == "on-disk")
    monkeypatch.setattr(atrain_cli, "model_url", lambda model: URL)
    return cli_events


def test_init_logs_its_downloads(init_stubs, monkeypatch):
    """The Flatpak runs `aTrain init` on its first start to fetch the required models."""
    monkeypatch.setattr(atrain_cli, "get_model", lambda model: "path")

    atrain_cli.init()

    assert init_stubs == [
        ("model_download_started", {"model": "m", "url": URL}),
        ("model_download_finished", {"model": "m", "checksum": "ok"}),
    ]


def test_init_logs_a_failed_checksum(init_stubs, monkeypatch):
    def mismatch(model):
        raise ModelIntegrityError("does not match its checksums")

    monkeypatch.setattr(atrain_cli, "get_model", mismatch)

    with pytest.raises(ModelIntegrityError):
        atrain_cli.init()

    assert init_stubs[-1] == (
        "model_download_failed",
        {
            "model": "m",
            "error": "ModelIntegrityError: does not match its checksums",
            "checksum": "failed",
        },
    )
