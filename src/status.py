import json
import os
from logging import Logger
from typing import Optional

from pydantic import BaseModel, ValidationError

__all__ = [
    'Status',
]


class Status(BaseModel):
    downloaded: bool = False
    digest_generated: bool = False
    oss_uploaded: bool = False
    oss_url: Optional[str] = None
    oss_images_uploaded: bool = False
    email_sent: bool = False
    telegram_sent: bool = False
    x_post_id: Optional[str] = None

    @classmethod
    def load(cls, path: str, logger: Optional[Logger] = None) -> 'Status':
        if not os.path.isfile(path):
            return cls()

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.model_validate(data)
        except (json.JSONDecodeError, ValidationError, OSError) as e:
            if logger is not None:
                logger.warning(
                    f'Failed to load status from {path}, treating as fresh: {e}'
                )
            return cls()

    def save(self, path: str) -> None:
        tmp_path = f'{path}.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
