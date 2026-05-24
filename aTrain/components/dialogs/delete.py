from aTrain.utils.archive import delete_transcription as delete
from nicegui import ui


def dialog_delete():
    with ui.dialog(value=True) as dialog, ui.card().classes("p-8"):
        dialog.props("persistent")
        ui.label("Are you sure you want to delete all transcriptions?")
        ui.separator()
        with ui.row().classes("w-full justify-end"):
            btn_cancel = ui.button("Cancel", color="gray-100").on_click(dialog.close)
            btn_cancel.props("unelevated no-caps text-color=dark")
            btn_confirm = ui.button("Confirm", color="dark")
            btn_confirm.props("unelevated no-caps")
            btn_confirm.on_click(lambda: (delete("all"), ui.navigate.reload()))
