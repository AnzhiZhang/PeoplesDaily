import json
import os
import threading
from logging import Logger
from typing import Optional

from pydantic import BaseModel, ValidationError

__all__ = [
    'Status',
    'load_status',
    'save_status',
]


class Status(BaseModel):
    downloaded: bool = False
    digest_generated: bool = False
    oss_uploaded: bool = False
    oss_url: Optional[str] = None
    email_sent: bool = False
    telegram_sent: bool = False
    telegram_digest_sent: bool = False


# save status lock
_save_lock = threading.Lock()


def load_status(path: str, logger: Optional[Logger] = None) -> Status:
    if not os.path.isfile(path):
        return Status()

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return Status.model_validate(data)
    except (json.JSONDecodeError, ValidationError, OSError) as e:
        if logger is not None:
            logger.warning(
                f'Failed to load status from {path}, treating as fresh: {e}'
            )
        return Status()


def save_status(status: Status, path: str) -> None:
    tmp_path = f'{path}.tmp'
    with _save_lock:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(status.model_dump(), f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
