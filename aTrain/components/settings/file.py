import os

from aTrain_core.globals import FLATPAK
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

    if not FLATPAK:
        # Use pywebview's native file dialog instead of NiceGUI's JS-side
        # uploader.pick_files() (which calls input.click() on a hidden <input
        # type="file">). On WebKitGTK (the default Linux backend since #161
        # switched from pywebview[qt] to pywebview[GTK]) programmatic file-input
        # clicks are blocked unless they fire synchronously in the user-click
        # call stack — and NiceGUI's run_method round-trip never is. The
        # pywebview dialog bypasses the WebKit input.click() rule entirely.
        with file_column:
            file_label = ui.label("No file selected").classes("text-sm text-gray-500")

        uploader.selected_content = None
        uploader.selected_name = None
        uploader.selected_path = None
        select_button.text = "Select File"

        async def on_pick():
            from nicegui import app

            main_window = getattr(getattr(app, "native", None), "main_window", None)
            if main_window is None:
                # Browser mode (no native window) — fall back to the JS picker.
                uploader.pick_files()
                return

            # Pass dialog_type=10 explicitly (=== webview.OPEN_DIALOG). DON'T use
            # the constant — it is a `proxy_tools.Proxy` lazy wrapper emitting
            # a deprecation warning, and it fails to pickle across the
            # multiprocessing boundary into pywebview's worker process with
            # "not the same object as webview.OPEN_DIALOG".
            # file_types format is dictated by pywebview's parse_file_type:
            # "Description (*.ext;*.ext)" with word-only description (no "/"!).
            pywebview_formats = ";".join(f"*{ext}" for ext in load_formats())
            result = await main_window.create_file_dialog(
                dialog_type=10,
                file_types=(f"Audio and Video ({pywebview_formats})", "All files (*.*)"),
            )
            if not result:
                return
            path = result[0] if isinstance(result, (list, tuple)) else result
            uploader.selected_path = path
            uploader.selected_name = os.path.basename(path)
            file_label.text = uploader.selected_name

        select_button.on_click(on_pick)
        return uploader

    with file_column:
        file_label = ui.label("No file selected").classes("text-sm text-gray-500")

    uploader.selected_content = None
    uploader.selected_name = None
    uploader.selected_path = None
    select_button.text = "Select File"

    def pick_file_native() -> str | None:
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

    def on_pick():
        path = pick_file_native()
        if not path:
            return
        uploader.selected_path = path
        uploader.selected_name = os.path.basename(path)
        file_label.text = uploader.selected_name

    select_button.on_click(on_pick)

    return uploader
