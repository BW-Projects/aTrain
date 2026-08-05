"""Regression tests for the Linux/Flatpak native file picker.

The XDG portal dialog blocks until the user picks or cancels. The click
handler must therefore dispatch it to a worker thread: if it ran on the
server's event loop, the whole app would freeze while the picker is open
(no websocket heartbeats -> the client shows "Connection lost").

`pick_file_native` is replaced by a fake that blocks on a threading.Event
just like the real portal call blocks on its GLib loop; the test then
interacts with the page while the pick is pending to prove the event loop
keeps serving, releases the fake, and checks the selection lands.
"""

import asyncio
import threading

import aTrain.pages.transcribe as transcribe_page
import aTrain_core.transcribe  # noqa: F401  pre-import so the splash import is instant
import pytest
from aTrain.components.settings import file as file_component
from nicegui import app, ui
from nicegui.testing import User

pytestmark = pytest.mark.module_under_test(transcribe_page)


@pytest.fixture
def blocking_pick(monkeypatch):
    """Fake portal dialog: blocks in its worker thread until released."""
    release = threading.Event()

    def fake_pick():
        assert release.wait(timeout=5), "test never released the fake picker"
        return "/home/user/recordings/audio.mp3"

    monkeypatch.setattr(file_component, "pick_file_native", fake_pick)
    return release


async def test_ui_stays_responsive_while_picker_is_open(user: User, blocking_pick):
    await user.open("/")
    await user.should_see("Select File", retries=100)

    user.find(kind=ui.button, content="Select File").click()
    await asyncio.sleep(0.1)  # let the pick task start and park in its thread

    # The pick is still pending (fake not released) - the page must still
    # process interactions. Before the fix, pick_file_native ran on the
    # event loop and this toggle would never be handled.
    user.find(marker="switch_speaker_detection").click()
    assert app.storage.general["speaker_detection"] is True

    blocking_pick.set()
    await user.should_see("audio.mp3", retries=100)


async def test_cancelled_pick_keeps_previous_state(user: User, monkeypatch):
    monkeypatch.setattr(file_component, "pick_file_native", lambda: None)
    await user.open("/")
    await user.should_see("Select File", retries=100)
    user.find(kind=ui.button, content="Select File").click()
    await asyncio.sleep(0.1)
    await user.should_see("No file selected")
