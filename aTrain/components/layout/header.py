from importlib.resources import files
from pathlib import Path
from typing import cast

from aTrain.version import __version__
from nicegui import ui

ATRAIN_LOGO = cast(Path, files("aTrain") / "static" / "images" / "logo.svg")
GITHUB_LOGO = cast(Path, files("aTrain") / "static" / "images" / "github.svg")
GITHUB_LINK = "https://github.com/JuergenFleiss/aTrain"


def header(drawer_handle: ui.drawer):
    with ui.header().classes("bg-white justify-between items-center px-10"):
        with ui.row().classes("items-center"):
            with ui.button().classes("lt-md") as menu_button:
                menu_button.props("color=white text-color=black icon=menu flat")
                menu_button.on_click(lambda: drawer_handle.toggle())
            ui.image(ATRAIN_LOGO).props("height=30px width=80px fit=contain")
        with ui.row().classes("items-center"):
            ui.image(GITHUB_LOGO).props("height=25px width=25px fit=contain")
            with ui.link(target=GITHUB_LINK, new_tab=True).classes("text-black"):
                ui.label(f"Version {__version__}")
