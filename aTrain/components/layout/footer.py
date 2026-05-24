from importlib.resources import files
from pathlib import Path
from typing import cast

from nicegui import ui

BANDAS_LOGO = cast(Path, files("aTrain") / "static" / "images" / "Bandas_Logo.svg")
PAPER_TEXT = "Using aTrain for research? Please cite our paper:"
PAPER_TITLE = (
    "Take the aTrain. Introducing an interface for the Accessible Transcription of Interviews"
)
PAPER_LINK = "https://doi.org/10.1016/j.jbef.2024.100891"


def footer():
    footer_classes = "bg-white justify-between items-center p-10"
    with ui.footer(wrap=False, fixed=False).classes(footer_classes):
        ui.image(BANDAS_LOGO).props("height='50px' width='150px' fit='contain'")
        with ui.column(align_items="end", wrap=True).classes("gap-0"):
            ui.label(PAPER_TEXT).classes("text-black")
            ui.link(PAPER_TITLE, target=PAPER_LINK, new_tab=True)
