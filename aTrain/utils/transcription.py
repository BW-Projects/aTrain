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
from aTrain_core.settings import ComputeType, Device, Settings, check_inputs_transcribe
from nicegui import app, events, run, ui
from nicegui.elements.upload_files import FileUpload
from nicegui.run import SubprocessException
from nicegui.run import setup as setup_process_pool
from starlette.formparsers import MultiPartParser

MultiPartParser.spool_max_size = 1024 * 1024 * 1024 * 10  # 10 GB file size limit


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
    upload: FileUpload | None = None
    path: Path | None = None

    async def materialise(self, directory: Path, filename: str) -> Path:
        """Return a path the engine can read, staging the upload if needed."""
        if self.path is not None:
            return self.path  # already on disk - no copy, the picker gave us a real file
        if self.upload is None:
            raise ValueError(f"No file to transcribe: {self.name!r} has neither upload nor path")
        # Stream to disk rather than into memory: MultiPartParser.spool_max_size
        # above allows 10 GB uploads.
        target = directory / filename
        await self.upload.save(target)
        return target


async def start_transcription(file: events.UploadEventArguments):
    """NiceGUI `on_upload` handler (browser upload path)."""
    await run_transcription(UploadPayload(name=file.file.name, upload=file.file))


async def start_transcription_from_path(path: Path, name: str):
    """Entry point for the native file picker (Linux/Flatpak path)."""
    await run_transcription(UploadPayload(name=name, path=path))


async def run_transcription(payload: UploadPayload):
    # Lazy import for improved startup speed
    from aTrain_core.transcribe import prepare_transcription, transcribe

    file_id: str | None = None
    with Manager() as manager, TemporaryDirectory() as tmp_dir:
        progress = manager.dict({"task": "Prepare", "current": 0, "total": 999999})
        dialog_process(progress)
        state = cast(State, app.storage.general)
        try:
            safe_file, file_id, timestamp = prepare_transcription(Path(payload.name))
            source = await payload.materialise(Path(tmp_dir), safe_file.name)
            settings = Settings(
                file=source,
                file_id=file_id,
                file_name=payload.name,
                model=state.get("model"),
                language=state.get("language"),
                speaker_detection=state.get("speaker_detection"),
                speaker_count=int(state.get("speaker_count") or 0) or None,
                device=Device.GPU if state.get("GPU") else Device.CPU,
                compute_type=ComputeType(state.get("compute_type")),
                timestamp=timestamp,
                temperature=state.get("temperature_override"),
                initial_prompt=state.get("initial_prompt") or None,
                cpu_threads=int(state.get("cpu_threads", 0)) or 0,
                progress=progress,
            )
            check_inputs_transcribe(
                settings.file_name, settings.model, settings.language, settings.device
            )
            await run.cpu_bound(transcribe, settings=settings)
            close_dialog_process()
            dialog_finished(file_id)

        except BrokenProcessPool:
            if file_id is not None:
                delete_transcription(file_id)
            setup_process_pool()
            close_dialog_process()
            ui.navigate.reload()

        except SubprocessException as e:
            close_dialog_process()
            dialog_error(error=e.original_message, traceback=e.original_traceback)

        except Exception as e:
            close_dialog_process()
            dialog_error(error=str(e), traceback=traceback.format_exc())
