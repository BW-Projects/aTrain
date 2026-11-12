import asyncio
import logging
import os
import traceback
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import Manager

from aTrain.components.dialogs.download import close_dialog_download, dialog_download
from aTrain.components.dialogs.error import dialog_error
from aTrain_core.event_log import log_event
from aTrain_core.globals import MODELS_DIR, REQUIRED_MODELS_DIR
from aTrain_core.load_resources import (
    get_model,
    load_model_config_file,
    model_is_complete,
    model_url,
    remove_model,
)
from aTrain_core.settings import load_languages
from huggingface_hub.utils import get_session
from nicegui import run, ui
from nicegui.run import SubprocessException
from nicegui.run import setup as setup_process_pool


def read_downloaded_models() -> list:
    # The two dirs coincide when REQUIRED_MODELS_DIR falls back to MODELS_DIR
    # (no bundled models); dedupe so models aren't listed twice.
    models_config = load_model_config_file()
    directories_to_search = list(dict.fromkeys([MODELS_DIR, REQUIRED_MODELS_DIR]))
    all_downloaded_models = []

    for directory in directories_to_search:
        os.makedirs(directory, exist_ok=True)
        all_file_directories = [
            dir_entry.name for dir_entry in os.scandir(directory) if dir_entry.is_dir()
        ]
        all_file_directories.sort(reverse=True)

        for directory_name in all_file_directories:
            directory_path = os.path.join(directory, directory_name)
            for file in os.listdir(directory_path):
                if file.endswith(".bin") and directory_name in list(models_config.keys()):
                    all_downloaded_models.append(directory_name)
                    break
                if (
                    file == "model.safetensors"
                    and models_config.get(directory_name, {}).get("backend")
                    == "crisper-transformers"
                ):
                    all_downloaded_models.append(directory_name)
                    break

    return all_downloaded_models


def read_transcription_models() -> list:
    all_models = read_downloaded_models()
    while "diarize" in all_models:
        all_models.remove("diarize")
    return all_models


def read_model_metadata() -> list:
    model_metadata = load_model_config_file()
    all_models = list(model_metadata.keys())
    downloaded_models = read_downloaded_models()
    all_models_metadata = []

    for model in all_models:
        model_info = {
            "model": model,
            "display_name": model_metadata[model].get("display_name", model),
            "group": model_metadata[model].get("group", "All others"),
            "size": model_metadata[model]["repo_size_human"],
            "downloaded": model in downloaded_models,
            # Only Hugging Face for now; an internal source (#322) goes here.
            "source": "Hugging Face",
            "source_url": (
                f"https://huggingface.co/{model_metadata[model]['repo_id']}"
                f"/tree/{model_metadata[model]['revision']}"
            ),
        }
        if info := model_metadata[model].get("info"):
            model_info["info"] = info
        all_models_metadata.append(model_info)

    all_models_metadata = sorted(all_models_metadata, key=lambda x: x["downloaded"], reverse=True)

    return all_models_metadata


def model_languages(model: str) -> dict:
    languages_dict = load_languages()
    all_models_configs = load_model_config_file()
    model_config: dict = all_models_configs[model]
    if "languages" in model_config.keys():
        languages: list = model_config["languages"]
        languages_dict = {language: languages_dict[language] for language in languages}
    return languages_dict


async def download_model(model: str):
    # True from model_download_started until the end of that download is logged.
    download_open = False
    with Manager() as manager:
        progress = manager.dict({"current": 0, "total": 999999})
        dialog_download(progress, model)
        try:
            # get_model() fetches nothing for a model that is already complete.
            if not model_is_complete(model):
                log_event("model_download_started", model=model, url=model_url(model))
                download_open = True
            check_internet()
            try:
                model_path = await run.cpu_bound(get_model, model=model, progress=progress)
            except asyncio.CancelledError:
                # NiceGUI 4 raises this where NiceGUI 3 returns None, see below.
                if download_open:
                    log_event("model_download_stopped", model=model)
                raise
            if download_open:
                download_open = False
                # NiceGUI 3 returns None when get_model() never ran: after a stop
                # while no worker ran, or when the server shuts down.
                if model_path is None:
                    log_event("model_download_stopped", model=model)
                else:
                    log_event("model_download_finished", model=model, checksum="ok")
            close_dialog_download()
            ui.navigate.reload()

        except BrokenProcessPool:
            if download_open:
                log_event("model_download_stopped", model=model)
            remove_model(model)
            setup_process_pool()
            close_dialog_download()
            ui.navigate.reload()

        except SubprocessException as e:
            if download_open:
                checksum = (
                    {"checksum": "failed"} if e.original_type == "ModelIntegrityError" else {}
                )
                error = f"{e.original_type}: {e.original_message}"
                log_event(
                    "model_download_failed", logging.ERROR, model=model, error=error, **checksum
                )
            remove_model(model)
            close_dialog_download()
            dialog_error(error=e.original_message, traceback=e.original_traceback)

        except Exception as e:
            if download_open:
                error = f"{type(e).__name__}: {e}"
                log_event("model_download_failed", logging.ERROR, model=model, error=error)
            remove_model(model)
            close_dialog_download()
            dialog_error(str(e), traceback.format_exc())


def check_internet() -> None:
    """A function to check whether the user is connected to the internet."""
    try:
        get_session().head("https://huggingface.co", timeout=10)
    except Exception as e:
        raise ConnectionError(
            f"We cannot reach Hugging Face ({e}). Most likely you are not connected to the internet."
        )
