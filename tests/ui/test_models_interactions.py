"""Interaction tests for the /models page.

Drives the Download / Delete buttons on the models page through the
NiceGUI in-process `user` fixture, asserting the page calls the right
backend function with the right argument. The page reads from
`read_model_metadata` and clicks invoke `download_model` /
`remove_model`; all three are monkeypatched so the test doesn't hit
HuggingFace, doesn't spawn a CPU-bound worker for an actual download,
and doesn't depend on which models are present on the host.
"""

import pytest
from aTrain.utils import models as models_utils
from nicegui import ui
from nicegui.testing import User


def _fake_metadata():
    """A predictable mix: one downloaded model (large-v1) and one not
    downloaded (tiny). Both are outside REQUIRED_MODELS so the page
    actually renders them as rows."""
    return [
        {"model": "tiny", "size": "75 MB", "downloaded": False},
        {"model": "large-v1", "size": "3 GB", "downloaded": True},
    ]


@pytest.fixture
def mocked_models(monkeypatch):
    """Pin the models the page sees, and record any download/remove calls.

    Patched on the persistent utils module: the page module is re-imported
    fresh per test by tests/ui/main.py and copies these names at import
    time, so this fixture must be listed before `user` in test signatures."""
    download_calls = []
    remove_calls = []

    def _record_download(model):
        # The real download_model is async, but the on_click handler returns
        # whatever the lambda returns and NiceGUI awaits coroutines for us
        # on the live server. In the user fixture the await chain isn't
        # synchronously driven, so we record via a synchronous stub.
        download_calls.append(model)

    def _record_remove(model):
        remove_calls.append(model)

    monkeypatch.setattr(models_utils, "read_model_metadata", _fake_metadata)
    monkeypatch.setattr(models_utils, "download_model", _record_download)
    monkeypatch.setattr(models_utils, "remove_model", _record_remove)
    return download_calls, remove_calls


async def test_models_page_lists_non_required_models(mocked_models, user: User):
    await user.open("/models")
    await user.should_see("Model Manager", retries=100)
    await user.should_see("tiny")
    await user.should_see("large-v1")
    await user.should_see("75 MB")
    await user.should_see("3 GB")


async def test_download_button_invokes_download_model(mocked_models, user: User):
    download_calls, _ = mocked_models
    await user.open("/models")
    await user.should_see("Model Manager", retries=100)
    # Exactly one row is not-downloaded → exactly one "Download" button.
    # kind= keeps the header label "Download Size" out of the match set:
    # nicegui>=3 clicks only the lowest-id match instead of all matches,
    # and a positional string target would ignore `kind` entirely.
    user.find(kind=ui.button, content="Download").click()
    assert download_calls == ["tiny"]


async def test_delete_button_invokes_remove_model(mocked_models, user: User):
    _, remove_calls = mocked_models
    await user.open("/models")
    await user.should_see("Model Manager", retries=100)
    # Exactly one row is downloaded → exactly one "Delete" button.
    user.find("Delete").click()
    assert remove_calls == ["large-v1"]
