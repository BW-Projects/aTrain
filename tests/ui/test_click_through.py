"""Full UI E2E via NiceGUI's in-process User fixture (no browser).

Renders the real transcription page and drives a transcription through the
app's real wiring (start_transcription -> run.cpu_bound -> finished dialog),
with the tiny model on CPU. Complements the lighter boot-serve smoke.
"""

from pathlib import Path
from typing import cast

import aTrain_core.transcribe  # noqa: F401  pre-import so the splash import is instant
from aTrain.utils.transcription import start_transcription, start_transcription_from_path
from nicegui import app, events
from nicegui.elements.upload_files import SmallFileUpload
from nicegui.testing import User

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_short.mp3"


async def test_main_page_renders(user: User):
    await user.open("/")
    await user.should_see("Start", retries=100)


CHEAP_SETTINGS = {
    "model": "tiny",
    "language": "auto-detect",
    "speaker_detection": False,
    "speaker_count": 0,
    "GPU": False,
    "compute_type": "int8",
    "temperature_override": None,
    "initial_prompt": None,
    "cpu_threads": 0,
}


async def test_transcribe_through_ui(user: User):
    """Browser-upload path (Windows/macOS): NiceGUI hands us an upload event."""
    await user.open("/")
    # The UI settings components write into app.storage.general; set them
    # directly to force the cheap path (tiny model, CPU) over the UI default.
    app.storage.general.update(CHEAP_SETTINGS)
    # start_transcription is exactly what the upload handler calls. Build a
    # *real* UploadEventArguments rather than a stand-in: a hand-rolled double
    # freezes whatever attribute names NiceGUI happened to use when it was
    # written, so an upload-API change (2.x `.name`/`.content` -> 3.x `.file`)
    # slips through green. sender/client are unused by the handler.
    upload_event = events.UploadEventArguments(
        sender=cast(object, None),  # type: ignore[arg-type]
        client=cast(object, None),  # type: ignore[arg-type]
        file=SmallFileUpload(
            name="sample_short.mp3",
            content_type="audio/mpeg",
            _data=FIXTURE.read_bytes(),
        ),
    )
    with user:
        await start_transcription(upload_event)
    await user.should_see("transcribed your file", retries=600)


async def test_transcribe_from_picked_path(user: User):
    """Native-picker path (Linux/Flatpak): the Start button hands us a path.

    This second entry point bypasses NiceGUI's upload entirely. CI runs on
    Linux, where `transcribe.py` wires *only* this branch - so without this
    test the browser-upload branch above is the one never exercised on CI,
    and vice versa on Windows. Both need covering, independently of platform.
    """
    await user.open("/")
    app.storage.general.update(CHEAP_SETTINGS)
    with user:
        await start_transcription_from_path(FIXTURE, FIXTURE.name)
    await user.should_see("transcribed your file", retries=600)
