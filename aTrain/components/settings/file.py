import asyncio
import os

from aTrain_core.globals import FLATPAK, LINUX
from aTrain_core.settings import load_formats
from nicegui import ui


class CustomUpload(ui.upload):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on("added", self.set_added)
        self.set_select()

    def pick_files(self):
        self.reset()
        self.set_select()
        self.run_method("pickFiles")

    def upload(self):
        self.run_method("upload")

    def set_added(self):
        self.file_text = "1 File Added"
        self.file_icon = "file_present"

    def set_select(self):
        self.file_text = "Select File"
        self.file_icon = "attach_file"


def pick_file_native() -> str | None:
    """Open the XDG desktop portal file chooser and block until it closes.

    Runs a GLib main loop until the portal's Response signal arrives, so this
    must never be called on the server's event loop - dispatch it to a worker
    thread (see `on_pick` in `input_file`).
    """
    try:
        import gi  # type: ignore

        gi.require_version("Gio", "2.0")
        gi.require_version("GLib", "2.0")
        from gi.repository import Gio, GLib  # type: ignore

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.FileChooser",
            None,
        )

        token = f"atrain{os.getpid()}"
        options = {
            "handle_token": GLib.Variant("s", token),
            "multiple": GLib.Variant("b", False),
            "directory": GLib.Variant("b", False),
        }

        result = proxy.call_sync(
            "OpenFile",
            GLib.Variant("(ssa{sv})", ("", "Select File", options)),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        handle = result.unpack()[0]

        request = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.portal.Desktop",
            handle,
            "org.freedesktop.portal.Request",
            None,
        )

        filename: str | None = None
        loop = GLib.MainLoop()

        def on_response(_proxy, _sender, _signal, params):
            nonlocal filename
            response, results = params.unpack()
            if response == 0:
                uris = results.get("uris")
                if uris:
                    uri = uris[0]
                    filename = Gio.File.new_for_uri(uri).get_path()
            loop.quit()

        request.connect("g-signal", on_response)
        loop.run()
        return filename
    except Exception as exc:
        print(f"Flatpak portal file dialog failed: {exc}")
        return None


def input_file() -> CustomUpload:
    allowed_files = "".join(x for x in str(load_formats()) if x not in "[]'")
    uploader = CustomUpload().classes("hidden")
    uploader.props(f"accept='{allowed_files}'")

    with ui.column().classes("gap-2") as file_column:
        ui.label("Select File").classes("font-bold text-dark text-md")
        ui.separator()
        with ui.button() as select_button:
            select_button.props("color=gray-100 text-color=dark align=left")
            select_button.props("unelevated no-caps :ripple=false")
            select_button.classes("w-full h-full")

    if not (FLATPAK or LINUX):
        select_button.bind_text(uploader, "file_text")
        select_button.bind_icon(uploader, "file_icon")
        select_button.on_click(uploader.pick_files)
        return uploader

    with file_column:
        file_label = ui.label("No file selected").classes("text-sm text-gray-500")

    uploader.selected_content = None
    uploader.selected_name = None
    uploader.selected_path = None
    select_button.text = "Select File"

    async def on_pick():
        # Re-entry guard: the portal dialog is not parented to our window
        # (OpenFile gets an empty parent handle), so nothing OS-level stops a
        # second click from opening a second dialog. Disable the button while
        # a pick is pending instead.
        if not select_button.enabled:
            return
        select_button.disable()
        try:
            # The portal dialog blocks until the user picks or cancels; run
            # it in a worker thread so the server's event loop keeps serving
            # (a blocked loop stops websocket heartbeats and the client shows
            # "Connection lost" while the picker is open). Plain
            # asyncio.to_thread instead of run.io_bound: nicegui's thread
            # pool is shut down by the stop button's tear_down and never
            # rebuilt, and this picker must still work afterwards.
            path = await asyncio.to_thread(pick_file_native)
        finally:
            select_button.enable()
        if not path:
            return
        uploader.selected_path = path
        uploader.selected_name = os.path.basename(path)
        file_label.text = uploader.selected_name

    select_button.on_click(on_pick)

    return uploader
