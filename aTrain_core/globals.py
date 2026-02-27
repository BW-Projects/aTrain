import multiprocessing as mp
import os
import platform
from importlib.resources import files
from importlib.util import find_spec
from pathlib import Path
from typing import cast

from platformdirs import user_data_path, user_documents_path

FLATPAK = bool(os.environ.get("FLATPAK_ID"))
SNAP = bool(os.environ.get("SNAP")) or bool(os.environ.get("SNAP_ID"))
# pyannote requires an explicit opt-in/out for telemetry metrics
if FLATPAK or SNAP:
    os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "false")

# Keep `spawn` for Snap and Flatpak x86; avoid forcing it on Flatpak ARM.
if SNAP or (FLATPAK and platform.machine().lower() not in {"aarch64", "arm64"}):
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
if SNAP and os.environ.get("ATRAIN_USER_DIR"):
    ATRAIN_DIR = Path(os.environ["ATRAIN_USER_DIR"])
else:
    ATRAIN_DIR = user_documents_path() / "aTrain"
MODELS_DIR = (user_data_path() / "models") if (FLATPAK or SNAP) else (ATRAIN_DIR / "models")
if FLATPAK or SNAP:
    REQUIRED_MODELS_DIR = MODELS_DIR
elif find_spec("aTrain"):
    REQUIRED_MODELS_DIR = cast(Path, files("aTrain") / "required_models")
else:
    REQUIRED_MODELS_DIR = MODELS_DIR
REQUIRED_MODELS = ["speaker-detection", "large-v3-turbo"]
TRANSCRIPT_DIR = ATRAIN_DIR / "transcriptions"
METADATA_FILENAME = "metadata.txt"
LOG_FILENAME = "log.txt"
TIMESTAMP_FORMAT = "%Y-%m-%d %H-%M-%S"
SAMPLING_RATE = 16000
DEFAULT_CPU_THREADS = max(1, count - 1) if (count := os.cpu_count()) else 4
MAX_CPU_THREADS = os.cpu_count() or DEFAULT_CPU_THREADS
