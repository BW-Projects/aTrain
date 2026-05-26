from aTrain.layouts.base import base_layout
from aTrain.utils.archive import load_faqs
from nicegui import ui


@ui.page("/faq")
def page():
    faqs = load_faqs()
    with base_layout():
        ui.label("Frequently Asked Questions").classes("text-lg text-dark font-bold")
        with ui.list().props("separator").classes("gap-3 w-full"):
            for faq in faqs:
                with ui.expansion(faq["question"], group="faq") as expansion:
                    expansion.classes("w-full").props("dense")
                    ui.label(faq["answer"]).classes("font-light")
