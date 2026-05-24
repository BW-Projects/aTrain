from nicegui import app, ui


def input_speaker_count():
    with ui.column().classes("gap-2") as column:
        ui.label("Number of Speakers").classes("font-bold text-dark text-md")
        ui.separator()

        with ui.row().classes("w-full gap-2 items-center"):
            input = ui.number(min=1, placeholder="Detect automatically")
            input.props("filled bg-color=gray-100 color=dark").classes("flex-grow")
            input.bind_value(app.storage.general, "speaker_count")

            reset_btn = ui.button(icon="refresh", color="gray-300")
            reset_btn.props("flat dense round size=sm").tooltip("Reset to default (auto-detect)")
            reset_btn.on_click(lambda: input.set_value(None))

    column.bind_visibility(app.storage.general, "speaker_detection")
