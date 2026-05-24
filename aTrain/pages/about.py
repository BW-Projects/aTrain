from aTrain.layouts.base import base_layout
from nicegui import ui

AUTHORS = ["Armin Haberl", "Jürgen Fleiß", "Dominik Kowald", "Stefan Thalmann"]
DEVELOPERS = ["Armin Haberl", "Jürgen Fleiß", "Andrea Forster (former)"]
MAIL = "mailto:atrain@uni-graz.at"
PRIVACY = "https://business-analytics.uni-graz.at/en/research/atrain/privacy-policy/"
LICENSE = "https://github.com/JuergenFleiss/aTrain/blob/main/LICENSE"


@ui.page("/about")
def page():
    with base_layout():
        ui.label("About aTrain").classes("text-lg text-dark font-bold")
        ui.separator()
        with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 w-full"):
            with ui.column().classes("gap-0"):
                ui.label("Initial Authors:").classes("font-bold")
                [ui.label(author) for author in AUTHORS]
            with ui.column().classes("gap-0"):
                ui.label("Main Developers:").classes("font-bold")
                [ui.label(developer) for developer in DEVELOPERS]
        ui.separator()
        ui.label("Disclaimer: aTrain is not an offical app of the University of Graz.")
        ui.separator()
        with ui.element("div").classes("grid grid-cols-1 md:grid-cols-3 gap-4 w-full"):
            with ui.link(target=MAIL, new_tab=True):
                btn_mail = ui.button("📧 Contact (Mail)", color="gray-100")
                btn_mail.props("text-color=dark no-caps unelevated")
                btn_mail.classes("w-full")
            with ui.link(target=PRIVACY, new_tab=True):
                btn_privacy = ui.button("🔒 Privacy Policy", color="gray-100")
                btn_privacy.props("text-color=dark no-caps unelevated")
                btn_privacy.classes("w-full")
            with ui.link(target=LICENSE, new_tab=True):
                btn_license = ui.button("📃 Software License", color="gray-100")
                btn_license.props("text-color=dark no-caps unelevated")
                btn_license.classes("w-full")
