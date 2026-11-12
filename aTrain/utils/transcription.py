import asyncio
import logging
import traceback
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from multiprocessing import Manager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict, cast

from aTrain.components.dialogs.error import dialog_error
from aTrain.components.dialogs.finished import dialog_finished
from aTrain.components.dialogs.process import close_dialog_process, dialog_process
from aTrain.utils.archive import delete_transcription
from aTrain_core.event_log import file_id_for_log, log_event
from aTrain_core.load_resources import model_is_complete, model_url
from aTrain_core.settings import ComputeType, Device, Settings, check_inputs_transcribe
from nicegui import app, events, run, ui
from nicegui.run import SubprocessException
from nicegui.run import setup as setup_process_pool


class State(TypedDict):
    model: str
    language: str
    speaker_detection: bool
    speaker_count: float | None
    GPU: bool
    compute_type: str
    temperature_override: float | None
    initial_prompt: str | None
    cpu_threads: int


@dataclass(slots=True)
class UploadPayload:
    """Platform-neutral description of the file to transcribe.

    Two callers feed the same pipeline: the browser upload on Windows/macOS
    (a NiceGUI `UploadEventArguments`) and the native file picker on
    Linux/Flatpak (a path on disk). Normalising both into this type keeps
    NiceGUI's event class out of the transcription code, so an upload-API
    change like 2.x `.name`/`.content` -> 3.x `.file` can only ever break the
    one adapter below instead of silently breaking one of the two platforms.
    """

    name: str
    upload: ui.upload.FileUpload | None = None
    path: Path | None = None

    async def materialise(self, directory: Path, filename: str) -> Path:
        """Return a path the engine can read, staging the upload if needed."""
        if self.path is not None:
            return self.path  # already on disk - no copy, the picker gave us a real file
        if self.upload is None:
            raise ValueError(f"No file to transcribe: {self.name!r} has neither upload nor path")
        target = directory / filename
        await self.upload.save(target)
        return target

    def extension(self) -> str:
        return Path(self.name).suffix.lower()

    def size(self) -> int | None:
        try:
            if self.path is not None:
                return self.path.stat().st_size
            return self.upload.size() if self.upload is not None else None
        except OSError:
            # The file can be gone by now. Log the event without a size instead of failing.
            return None


def _without_recording(text: str, file_id: str | None, *names: str | None) -> str:
    """Take the recording out of an error message before it is logged.

    Its path and file name become <file>. The file id keeps only its timestamp
    part, because the rest is the start of the file name.
    """
    for name in sorted({name for name in names if name}, key=len, reverse=True):
        text = text.replace(name, "<file>")
    if file_id:
        text = text.replace(file_id, file_id_for_log(file_id) or "")
    return text


async def start_transcription(file: events.UploadEventArguments):
    """NiceGUI `on_upload` handler (browser upload path)."""
    await run_pipeline(UploadPayload(name=file.file.name, upload=file.file))


async def start_transcription_from_path(path: Path, name: str):
    """Entry point for the native file picker (Linux/Flatpak path)."""
    await run_pipeline(UploadPayload(name=name, path=path))


async def run_pipeline(payload: UploadPayload):
    # Lazy import for improved startup speed
    from aTrain_core.transcribe import prepare_transcription, transcribe

    file_id: str | None = None
    # Every name of the recording that an error message can contain: its file name
    # and its paths.
    recording = [payload.name, str(payload.path) if payload.path else None]
    missing: list[str] = []
    checksum_failed: list[str] = []
    outcome_logged = False
    with Manager() as manager, TemporaryDirectory() as tmp_dir:
        progress = manager.dict({"task": "Prepare", "current": 0, "total": 999999})
        dialog_process(progress)
        # Snapshot rather than read live: the page re-renders while the upload is
        # staged, and `get_model_options` resets `model` to None whenever no model
        # is on disk yet. Reading through to the live storage would also let a user
        # switching the model mid-upload retarget a run that is already under way.
        state = cast(State, dict(app.storage.general))
        try:
            device = Device.GPU if state.get("GPU") else Device.CPU
            # Validate first: it needs nothing but the name and the settings, and
            # rejecting a wrong model or language should not cost a directory and
            # a full copy of the upload beforehand.
            try:
                check_inputs_transcribe(
                    payload.name, state.get("model"), state.get("language"), device
                )
            except ValueError as e:
                outcome_logged = True
                log_event(
                    "file_rejected",
                    logging.WARNING,
                    extension=payload.extension(),
                    size=payload.size(),
                    reason=_without_recording(str(e), None, *recording),
                )
                raise
            safe_file, file_id, timestamp = prepare_transcription(Path(payload.name))
            recording.append(safe_file.name)
            log_event(
                "file_accepted",
                file_id=file_id_for_log(file_id),
                extension=payload.extension(),
                size=payload.size(),
            )
            source = await payload.materialise(Path(tmp_dir), safe_file.name)
            recording.append(str(source))
            settings = Settings(
                file=source,
                file_id=file_id,
                file_name=payload.name,
                model=state.get("model"),
                language=state.get("language"),
                speaker_detection=state.get("speaker_detection"),
                speaker_count=int(state.get("speaker_count") or 0) or None,
                device=device,
                compute_type=ComputeType(state.get("compute_type")),
                timestamp=timestamp,
                temperature=state.get("temperature_override"),
                initial_prompt=state.get("initial_prompt") or None,
                cpu_threads=int(state.get("cpu_threads", 0)) or 0,
                progress=progress,
            )
            # The worker's get_model() downloads a missing model without telling the
            # server, so the server logs the download here.
            needed = [state.get("model")]
            if state.get("speaker_detection"):
                needed.append("speaker-detection")
            missing = [model for model in needed if not model_is_complete(model)]
            for model in missing:
                log_event("model_download_by_transcription", model=model, url=model_url(model))
            # Logged when the file goes to the worker. If the worker never runs,
            # transcription_stopped follows.
            log_event(
                "transcription_started",
                file_id=file_id_for_log(file_id),
                model=state.get("model"),
                device=device.value,
            )
            try:
                completed = await run.cpu_bound(transcribe, settings=settings)
            except asyncio.CancelledError:
                # NiceGUI 4 raises this where NiceGUI 3 returns None, see below.
                log_event("transcription_stopped", file_id=file_id_for_log(file_id))
                raise
            outcome_logged = True
            if completed is None:
                # NiceGUI 3 returns None when transcribe() never ran: after a stop
                # while no worker ran, or when the server shuts down.
                log_event("transcription_stopped", file_id=file_id_for_log(file_id))
            else:
                log_event("transcription_finished", file_id=file_id_for_log(file_id))
            close_dialog_process()
            dialog_finished(file_id)

        except BrokenProcessPool:
            log_event("transcription_stopped", file_id=file_id_for_log(file_id))
            if file_id is not None:
                delete_transcription(file_id)
            setup_process_pool()
            close_dialog_process()
            ui.navigate.reload()

        except SubprocessException as e:
            if e.original_type == "ModelIntegrityError":
                # The message of a ModelIntegrityError names its model in quotes.
                checksum_failed = [model for model in missing if f"'{model}'" in e.original_message]
            error = f"{e.original_type}: {e.original_message}"
            log_event(
                "transcription_failed",
                logging.ERROR,
                file_id=file_id_for_log(file_id),
                error=_without_recording(error, file_id, *recording),
            )
            close_dialog_process()
            dialog_error(error=e.original_message, traceback=e.original_traceback)

        except Exception as e:
            # A rejected file and a run that ended are in the log already. What
            # failed then is the dialog, not the transcription.
            if not outcome_logged:
                error = f"{type(e).__name__}: {e}"
                log_event(
                    "transcription_failed",
                    logging.ERROR,
                    file_id=file_id_for_log(file_id),
                    error=_without_recording(error, file_id, *recording),
                )
            close_dialog_process()
            dialog_error(error=str(e), traceback=traceback.format_exc())

        finally:
            # One end event for every model announced above. The server cannot see
            # whether the worker started the download, only what is on disk now.
            # get_model() verified a model that is complete.
            for model in missing:
                if model_is_complete(model):
                    log_event("model_download_finished", model=model, checksum="ok")
                elif model in checksum_failed:
                    log_event(
                        "model_download_incomplete", logging.ERROR, model=model, checksum="failed"
                    )
                else:
                    log_event("model_download_incomplete", model=model)
