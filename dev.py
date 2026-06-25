import os
from unittest.mock import patch
from aTrain_core.globals import ATRAIN_DIR, FLATPAK
from platformdirs import user_config_path

# Setup the NiceGUI storage path, mimicking the native app behavior
NICEGUI_STORAGE_PATH = user_config_path() / "aTrain" if FLATPAK else (ATRAIN_DIR / "settings")

with patch.dict(os.environ, NICEGUI_STORAGE_PATH=str(NICEGUI_STORAGE_PATH)):
    from nicegui import ui
    from aTrain.pages import about, archive, faq, models, transcribe  # Registers the UI pages

    if __name__ in {"__main__", "__mp_main__"}:
        ui.run(
            native=False,
            reload=True,
            title="aTrain (Dev Mode)",
        )
