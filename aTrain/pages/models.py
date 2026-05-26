from aTrain.layouts.base import base_layout
from aTrain.utils.models import download_model, read_model_metadata, remove_model
from aTrain_core.globals import REQUIRED_MODELS
from nicegui import ui


@ui.page("/models")
def page():
    all_models = read_model_metadata()
    models = [model for model in all_models if model["model"] not in REQUIRED_MODELS]
    with base_layout():
        ui.label("Model Manager").classes("text-lg text-dark font-bold")
        with ui.list().classes("w-full").props("separator"):
            with ui.item():
                with ui.grid(columns="minmax(0, 60px) 1fr 1fr 1fr") as grid:
                    grid.classes("w-full text-grey text-xs items-end")
                    ui.label("#")
                    ui.label("Model")
                    ui.label("Download Size")
                    ui.label("Actions")
            for i, model in enumerate(models):
                with ui.item().classes("hover:bg-gray-100"):
                    with ui.grid(columns="minmax(0, 60px) 1fr 1fr 1fr") as grid:
                        grid.classes("w-full items-center")
                        ui.label(str(i + 1)).classes("font-light")
                        ui.label(model["model"]).classes("font-medium")
                        ui.label(model["size"]).classes("font-light")
                        with ui.row():
                            if model["downloaded"]:
                                btn_delete = ui.button("Delete", color="gray-100")
                                btn_delete.props("no-caps size=0.7rem unelevated")
                                btn_delete.on_click(
                                    lambda m=model: (
                                        remove_model(m["model"]),
                                        ui.navigate.reload(),
                                    )
                                )
                            else:
                                btn_download = ui.button("Download", color="dark")
                                btn_download.props("no-caps size=0.7rem unelevated")
                                btn_download.on_click(lambda m=model: download_model(m["model"]))
