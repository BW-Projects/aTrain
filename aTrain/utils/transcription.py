import traceback
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import Manager
from pathlib import Path
from typing import TypedDict, cast

from aTrain_core.settings import ComputeType, Device, Settings, check_inputs_transcribe
from nicegui import app, events, run, ui
from nicegui.run import SubprocessException
from nicegui.run import setup as setup_process_pool
from starlette.formparsers import MultiPartParser

from aTrain.components.dialogs.error import dialog_error
from aTrain.components.dialogs.finished import dialog_finished
from aTrain.components.dialogs.process import close_dialog_process, dialog_process
from aTrain.utils.archive import delete_transcription

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


async def start_transcription(file: events.UploadEventArguments):
    # Lazy import for improved startup speed
    from aTrain_core.transcribe import prepare_transcription, transcribe

    with Manager() as manager:
        progress = manager.dict({"task": "Prepare", "current": 0, "total": 999999})
        dialog_process(progress)
        _, file_id, timestamp = prepare_transcription(Path(file.name))
        state = cast(State, app.storage.general)
        try:
            settings = Settings(
                file=file.content,
                file_id=file_id,
                file_name=file.name,
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
