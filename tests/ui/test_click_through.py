"""Full UI E2E via NiceGUI's in-process User fixture (no browser).

Renders the real transcription page and drives a transcription through the
app's real wiring (start_transcription -> run.cpu_bound -> finished dialog),
with the tiny model on CPU. Complements the lighter boot-serve smoke.
"""

from pathlib import Path
from types import SimpleNamespace

import aTrain_core.transcribe  # noqa: F401  pre-import so the splash import is instant
from aTrain.utils.transcription import start_transcription
from nicegui import app
from nicegui.testing import User

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_short.mp3"


async def test_main_page_renders(user: User):
    await user.open("/")
    await user.should_see("Start", retries=100)


async def test_transcribe_through_ui(user: User):
    await user.open("/")
    # The UI settings components write into app.storage.general; set them
    # directly to force the cheap path (tiny model, CPU) over the UI default.
    app.storage.general.update(
        {
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
    )
    # start_transcription is exactly what the upload handler calls; drive it
    # with a file payload (same shape as the upload event / the Flatpak path).
    with user:
        await start_transcription(SimpleNamespace(name="sample_short.mp3", content=FIXTURE))
    await user.should_see("transcribed your file", retries=600)
