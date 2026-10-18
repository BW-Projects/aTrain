"""The macOS native window picks the file with pywebview's own file dialog.

The web page's file dialog (`<input type="file">` behind "Select File") does
not open in pywebview's macOS window (#307), the same reason Linux and Flatpak
use a native picker. These tests pretend to be macOS on any CI platform.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import aTrain_core.globals
import aTrain_core.transcribe  # pre-import so the splash import is instant
import pytest
from aTrain.components.settings import file as file_component
from nicegui import app, ui
from nicegui.testing import User

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_short.mp3"


def fake_window(picked: tuple[str, ...] | None) -> Mock:
    """Stands in for NiceGUI's proxy of the native window."""
    window = Mock()
    window.create_file_dialog = AsyncMock(return_value=picked)
    return window


def pretend_macos(monkeypatch, window: Mock) -> None:
    # The page module is imported fresh per test and reads the globals then;
    # the component module persists, so patch its copies too.
    for module in (aTrain_core.globals, file_component):
        monkeypatch.setattr(module, "FLATPAK", False)
        monkeypatch.setattr(module, "LINUX", False)
        monkeypatch.setattr(module, "MACOS", True)
    monkeypatch.setattr(app.native, "main_window", window)


@pytest.fixture
def picks_fixture(monkeypatch) -> Mock:
    window = fake_window((str(FIXTURE),))
    pretend_macos(monkeypatch, window)
    return window


@pytest.fixture
def picks_nothing(monkeypatch) -> Mock:
    window = fake_window(None)  # the user cancelled the dialog
    pretend_macos(monkeypatch, window)
    return window


async def test_select_file_opens_the_native_dialog_on_macos(picks_fixture, user: User):
    await user.open("/")
    await user.should_see("Start", retries=100)

    user.find(kind=ui.button, content="Select File").click()

    await user.should_see(FIXTURE.name)
    picks_fixture.create_file_dialog.assert_awaited_once()


async def test_cancelled_dialog_selects_nothing(picks_nothing, user: User):
    await user.open("/")
    await user.should_see("Start", retries=100)

    user.find(kind=ui.button, content="Select File").click()
    for _ in range(50):  # the click is handled asynchronously
        if picks_nothing.create_file_dialog.await_count:
            break
        await asyncio.sleep(0.05)

    picks_nothing.create_file_dialog.assert_awaited_once()
    await user.should_see("No file selected")
