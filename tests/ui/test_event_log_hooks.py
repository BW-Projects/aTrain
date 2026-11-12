"""Which events aTrain logs around `aTrain start`, downloads and transcriptions (#339).

No server, no worker and no model runs, but the modules import nicegui, so these
live in tests/ui. log_event is replaced by a recorder, ui.run, the dialogs and the
worker pool by stubs.
"""

import asyncio
import contextlib
import sys
from concurrent.futures.process import BrokenProcessPool
from unittest.mock import Mock

import aTrain.app as atrain_cli
import aTrain_core.transcribe
import nicegui.error
import pytest
from aTrain.utils import models, transcription
from aTrain.version import __version__
from aTrain_core.integrity import ModelIntegrityError
from nicegui import app, run, ui
from nicegui.run import SubprocessException
from wakepy import keep

URL = "https://huggingface.co/org/m/tree/abc"


def _recorder(recorded):
    def record(event, level=None, **fields):
        recorded.append((event, fields))

    return record


@pytest.fixture
def cli_events(monkeypatch):
    """`aTrain start` without a log file, a server or a wake lock."""
    recorded = []
    monkeypatch.setattr(atrain_cli, "setup_event_log", Mock())
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
    monkeypatch.setattr(app, "on_page_exception", Mock())
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
    atrain_cli.setup_event_log.assert_called_once()
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


def test_a_failed_start_is_logged(cli_events, monkeypatch):
    """uvicorn ends a start on a taken port with sys.exit(1). SystemExit is not an Exception."""
    monkeypatch.setattr(ui, "run", Mock(side_effect=SystemExit(1)))

    with pytest.raises(SystemExit):
        _start()

    assert cli_events[-1] == ("server_failed", {"exit_code": 1})


def test_a_clean_exit_is_not_a_failure(cli_events, monkeypatch):
    monkeypatch.setattr(ui, "run", Mock(side_effect=SystemExit(0)))

    with pytest.raises(SystemExit):
        _start()

    assert "server_failed" not in [event for event, _ in cli_events]


def test_an_error_while_building_a_page_reaches_the_log(cli_events, monkeypatch):
    """Without a page exception handler NiceGUI shows its 500 page and skips the hook."""
    shown = Mock()
    monkeypatch.setattr(nicegui.error, "error_content", shown)
    _start()

    show_error_page = app.on_page_exception.call_args.args[0]
    error = RuntimeError("page failed")
    show_error_page(error)
    shown.assert_called_once_with(500, error)


async def _works(func, *args, **kwargs):
    return "done"


async def _stopped(func, *args, **kwargs):
    raise BrokenProcessPool()  # the dialog's stop button breaks a running worker


async def _not_run(func, *args, **kwargs):
    return None  # NiceGUI 3 after a stop while no worker ran, or at server shutdown


async def _cancelled(func, *args, **kwargs):
    raise asyncio.CancelledError()  # NiceGUI 4 in the same cases


async def _fails(func, *args, **kwargs):
    raise SubprocessException("OSError", "connection reset", "")


async def _bad_checksum(func, *args, **kwargs):
    raise SubprocessException("ModelIntegrityError", "does not match its checksums", "")


@pytest.fixture
def events(monkeypatch):
    recorded = []
    monkeypatch.setattr(models, "log_event", _recorder(recorded))
    monkeypatch.setattr(transcription, "log_event", _recorder(recorded))
    return recorded


@pytest.fixture
def download_stubs(monkeypatch, events):
    for name in (
        "dialog_download",
        "close_dialog_download",
        "dialog_error",
        "setup_process_pool",
        "remove_model",
    ):
        monkeypatch.setattr(models, name, Mock())
    monkeypatch.setattr(models, "check_internet", lambda: None)
    monkeypatch.setattr(models, "model_is_complete", lambda model: False)
    monkeypatch.setattr(models, "model_url", lambda model: URL)
    monkeypatch.setattr(ui.navigate, "reload", Mock())


DOWNLOAD_STARTED = ("model_download_started", {"model": "m", "url": URL})
DOWNLOAD_STOPPED = ("model_download_stopped", {"model": "m"})


@pytest.mark.parametrize(
    ("cpu_bound", "last_event"),
    [
        pytest.param(
            _works, ("model_download_finished", {"model": "m", "checksum": "ok"}), id="ok"
        ),
        pytest.param(_stopped, DOWNLOAD_STOPPED, id="stop"),
        pytest.param(_not_run, DOWNLOAD_STOPPED, id="not run"),
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
async def test_a_download_logs_its_start_and_its_end(
    download_stubs, events, monkeypatch, cpu_bound, last_event
):
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)

    await models.download_model("m")

    assert events == [DOWNLOAD_STARTED, last_event]


async def test_a_cancelled_download_is_logged_and_passed_on(download_stubs, events, monkeypatch):
    monkeypatch.setattr(run, "cpu_bound", _cancelled)

    with pytest.raises(asyncio.CancelledError):
        await models.download_model("m")

    assert events == [DOWNLOAD_STARTED, DOWNLOAD_STOPPED]


async def test_a_download_that_never_ran_changes_only_the_log(download_stubs, monkeypatch):
    """The dialog closes and the page reloads as before. The stop handling is #347."""
    monkeypatch.setattr(run, "cpu_bound", _not_run)

    await models.download_model("m")

    models.close_dialog_download.assert_called_once()
    ui.navigate.reload.assert_called_once()
    models.remove_model.assert_not_called()


async def test_a_failed_connectivity_check_is_a_failed_download(
    download_stubs, events, monkeypatch
):
    def offline():
        raise ConnectionError("We cannot reach Hugging Face")

    monkeypatch.setattr(models, "check_internet", offline)

    await models.download_model("m")

    assert events[-1] == (
        "model_download_failed",
        {"model": "m", "error": "ConnectionError: We cannot reach Hugging Face"},
    )


async def test_a_complete_model_logs_no_download_at_all(download_stubs, events, monkeypatch):
    """The models page offers "Download" for some complete models. Nothing is fetched then."""

    def offline():
        raise ConnectionError("We cannot reach Hugging Face")

    monkeypatch.setattr(models, "model_is_complete", lambda model: True)
    monkeypatch.setattr(models, "check_internet", offline)

    await models.download_model("m")

    assert events == []


async def test_a_failing_dialog_adds_no_second_end_to_a_download(
    download_stubs, events, monkeypatch
):
    monkeypatch.setattr(run, "cpu_bound", _works)
    monkeypatch.setattr(
        models, "close_dialog_download", Mock(side_effect=[RuntimeError("page is gone"), None])
    )

    await models.download_model("m")

    assert events == [
        DOWNLOAD_STARTED,
        ("model_download_finished", {"model": "m", "checksum": "ok"}),
    ]


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
    monkeypatch.setattr(ui.navigate, "reload", Mock())
    monkeypatch.setattr(transcription, "model_is_complete", lambda model: True)
    monkeypatch.setattr(transcription, "model_url", lambda model: URL)
    monkeypatch.setattr(
        aTrain_core.transcribe,
        "prepare_transcription",
        lambda file: (file, "2611121004-Intervi", "2026-11-12 10:04:00"),
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
    recording = tmp_path / "Interview_Maria_Mueller.MP3"
    recording.write_bytes(b"12345")
    return transcription.UploadPayload(name="Interview_Maria_Mueller.MP3", path=recording)


ACCEPTED = ("file_accepted", {"file_id": "2611121004", "extension": ".mp3", "size": 5})
STARTED = ("transcription_started", {"file_id": "2611121004", "model": "m", "device": "cpu"})
FINISHED = ("transcription_finished", {"file_id": "2611121004"})
STOPPED = ("transcription_stopped", {"file_id": "2611121004"})


@pytest.mark.parametrize(
    ("cpu_bound", "last_event"),
    [
        pytest.param(_works, FINISHED, id="ok"),
        pytest.param(_stopped, STOPPED, id="stop"),
        pytest.param(_not_run, STOPPED, id="not run"),
        pytest.param(
            _fails,
            (
                "transcription_failed",
                {"file_id": "2611121004", "error": "OSError: connection reset"},
            ),
            id="error",
        ),
    ],
)
async def test_a_transcription_logs_its_start_and_its_end(
    pipeline_stubs, payload, events, monkeypatch, cpu_bound, last_event
):
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)

    await transcription.run_pipeline(payload)

    assert events == [ACCEPTED, STARTED, last_event]


async def test_a_cancelled_transcription_is_logged_and_passed_on(
    pipeline_stubs, payload, events, monkeypatch
):
    monkeypatch.setattr(run, "cpu_bound", _cancelled)

    with pytest.raises(asyncio.CancelledError):
        await transcription.run_pipeline(payload)

    assert events == [ACCEPTED, STARTED, STOPPED]


async def test_a_transcription_that_never_ran_changes_only_the_log(
    pipeline_stubs, payload, monkeypatch
):
    """The finished dialog still opens. The stop handling is #347."""
    monkeypatch.setattr(run, "cpu_bound", _not_run)

    await transcription.run_pipeline(payload)

    transcription.dialog_finished.assert_called_once_with("2611121004-Intervi")
    transcription.setup_process_pool.assert_not_called()


async def test_the_file_name_and_the_initial_prompt_stay_out_of_the_log(
    pipeline_stubs, payload, events, monkeypatch
):
    monkeypatch.setattr(run, "cpu_bound", _works)

    await transcription.run_pipeline(payload)

    assert "Maria" not in str(events)
    assert "Intervi" not in str(events)
    assert "a secret prompt" not in str(events)


async def test_a_rejected_file_is_logged_without_its_name(
    pipeline_stubs, payload, events, monkeypatch
):
    cpu_bound = Mock(side_effect=_works)
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)
    monkeypatch.setattr(
        transcription, "check_inputs_transcribe", Mock(side_effect=ValueError("Incorrect input."))
    )

    await transcription.run_pipeline(payload)

    assert events == [
        ("file_rejected", {"extension": ".mp3", "size": 5, "reason": "Incorrect input."})
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
        ("file_rejected", {"extension": ".mp3", "size": None, "reason": "Incorrect input."})
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
        (
            "transcription_failed",
            {
                "file_id": None,
                "error": "PermissionError: the transcriptions folder is read-only",
            },
        )
    ]


@pytest.fixture
def speaker_detection(pipeline_stubs, monkeypatch):
    """Speaker detection is on and its model is missing until the worker fetched it."""
    app.storage.general["speaker_detection"] = True
    on_disk = {"m"}
    monkeypatch.setattr(transcription, "model_is_complete", lambda model: model in on_disk)
    return on_disk


FETCHING = ("model_download_by_transcription", {"model": "speaker-detection", "url": URL})


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
        FETCHING,
        STARTED,
        FINISHED,
        ("model_download_finished", {"model": "speaker-detection", "checksum": "ok"}),
    ]


INCOMPLETE = ("model_download_incomplete", {"model": "speaker-detection"})


@pytest.mark.parametrize(
    "cpu_bound",
    [
        pytest.param(_stopped, id="stop"),
        pytest.param(_not_run, id="not run"),
        pytest.param(_fails, id="error"),
        pytest.param(_works, id="finished without needing the model"),
    ],
)
async def test_a_model_that_is_still_missing_after_the_run_is_logged_as_incomplete(
    speaker_detection, payload, events, monkeypatch, cpu_bound
):
    """The server cannot see whether the worker started the download, only what is on disk."""
    monkeypatch.setattr(run, "cpu_bound", cpu_bound)

    await transcription.run_pipeline(payload)

    assert events[-1] == INCOMPLETE
    assert [event for event, _ in events].count("model_download_by_transcription") == 1


async def test_a_failed_checksum_inside_the_worker_is_logged_for_its_model(
    speaker_detection, payload, events, monkeypatch
):
    async def mismatch(func, *args, **kwargs):
        message = "Model 'speaker-detection' does not match its checksums and will be removed."
        raise SubprocessException("ModelIntegrityError", message, "")

    monkeypatch.setattr(run, "cpu_bound", mismatch)

    await transcription.run_pipeline(payload)

    assert events[-1] == (
        "model_download_incomplete",
        {"model": "speaker-detection", "checksum": "failed"},
    )


async def test_a_failing_dialog_adds_no_second_end_to_a_transcription(
    pipeline_stubs, payload, events, monkeypatch
):
    monkeypatch.setattr(run, "cpu_bound", _works)
    monkeypatch.setattr(
        transcription, "dialog_finished", Mock(side_effect=RuntimeError("page is gone"))
    )

    await transcription.run_pipeline(payload)

    assert events == [ACCEPTED, STARTED, FINISHED]


async def test_the_recording_is_replaced_in_a_logged_error(
    pipeline_stubs, payload, events, monkeypatch
):
    """Error messages of the worker often quote the path of the file they could not read."""

    async def cannot_decode(func, *args, **kwargs):
        message = (
            f"Invalid data in '{payload.path}', see transcriptions/2611121004-Intervi/log.txt "
            "(Interview_Maria_Mueller.MP3)"
        )
        raise SubprocessException("OSError", message, "")

    monkeypatch.setattr(run, "cpu_bound", cannot_decode)

    await transcription.run_pipeline(payload)

    assert events[-1] == (
        "transcription_failed",
        {
            "file_id": "2611121004",
            "error": "OSError: Invalid data in '<file>', see transcriptions/2611121004/log.txt "
            "(<file>)",
        },
    )


def test_the_size_of_a_browser_upload_is_read_from_the_upload():
    upload = Mock(size=Mock(return_value=7))

    assert transcription.UploadPayload(name="a.mp3", upload=upload).size() == 7


def test_transcribe_returns_the_file_id(monkeypatch):
    """run_pipeline tells a finished run from one that never ran by this return value."""
    for name in (
        "write_logfile",
        "create_metadata",
        "get_model",
        "run_transcription",
        "write_final_outputs",
    ):
        monkeypatch.setattr(aTrain_core.transcribe, name, Mock())
    monkeypatch.setattr(aTrain_core.transcribe, "load_audio", Mock(return_value=([], 1)))
    monkeypatch.setattr(aTrain_core.transcribe.engine, "backend_of", Mock(return_value="whisper"))
    settings = Mock(
        file_id="2611121004-Intervi",
        device=aTrain_core.transcribe.Device.CPU,
        speaker_detection=False,
    )

    assert aTrain_core.transcribe.transcribe(settings) == "2611121004-Intervi"


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

    atrain_cli.setup_event_log.assert_called_once()
    assert init_stubs == [
        DOWNLOAD_STARTED,
        ("model_download_finished", {"model": "m", "checksum": "ok"}),
    ]


def test_init_logs_a_download_stopped_with_ctrl_c(init_stubs, monkeypatch):
    monkeypatch.setattr(atrain_cli, "get_model", Mock(side_effect=KeyboardInterrupt()))

    with pytest.raises(KeyboardInterrupt):
        atrain_cli.init()

    assert init_stubs == [DOWNLOAD_STARTED, DOWNLOAD_STOPPED]


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
