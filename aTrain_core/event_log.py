"""Central log of security-relevant events (#339).

`aTrain start` calls setup_event_log() in the server process. Worker processes and
tests never do, so their log_event() calls go nowhere and only one process writes
the file: RotatingFileHandler is not safe across processes.

Transcript text and the initial prompt do not belong in this log.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aTrain_core.globals import LOG_DIR

LOG_FILENAME = "atrain.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 4  # with the current file, 5 files at most

logger = logging.getLogger("aTrain.events")
logger.setLevel(logging.INFO)
logger.propagate = False
logger.addHandler(logging.NullHandler())


def setup_event_log(log_dir: Path = LOG_DIR) -> Path | None:
    """Start writing events to a rotating file and return its path.

    Returns None if the folder is not writable: a missing log must not keep the
    app from starting.
    """
    path = log_dir / LOG_FILENAME
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
    except OSError as error:
        print(f"Cannot write the event log to {path}: {error}")
        return None
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S%z")
    )
    logger.addHandler(handler)
    return path


def log_event(event: str, level: int = logging.INFO, exc_info=None, **fields) -> None:
    """Write one event. repr() keeps a line break in a value from forging an entry."""
    details = " ".join(f"{key}={value!r}" for key, value in fields.items())
    logger.log(level, "%s", f"{event} {details}".rstrip(), exc_info=exc_info)


def log_unhandled_exception(error: Exception) -> None:
    log_event("unhandled_exception", logging.ERROR, exc_info=error, error=str(error))
