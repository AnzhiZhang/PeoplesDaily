from logging import Logger
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

FILE_PATH = 'config/config.yaml'


class DigestConfigSection(BaseModel):
    enabled: bool = False
    base_url: str = ''
    api_key: str = ''
    model: str = ''


class OSSConfigSection(BaseModel):
    enabled: bool = False
    access_key_id: str = ''
    access_key_secret: str = ''
    endpoint: str = ''
    bucket_name: str = ''
    is_cname: bool = False
    region: str = ''
    pretty_endpoint: Optional[str] = None


class EmailConfigSection(BaseModel):
    enabled: bool = False
    smtp_server: str = ''
    smtp_port: int = 0
    smtp_use_ssl: bool = False
    smtp_user: str = ''
    smtp_password: str = ''
    sender: str = ''
    recipients: List[str] = Field(default_factory=list)
    with_attachment: bool = False
    unsubscribe_address: Optional[str] = None


class TelegramConfigSection(BaseModel):
    enabled: bool = False
    bot_token: str = ''
    channel_id: int = 0
    discussion_chat_id: int = 0


class XConfigSection(BaseModel):
    enabled: bool = False
    username: str = ''
    client_id: str = ''
    client_secret: str = Field(default='', repr=False)
    refresh_token: str = Field(default='', repr=False)


class Config(BaseModel):
    cron_enabled: bool = False
    debug: bool = False

    digest: DigestConfigSection = Field(default_factory=DigestConfigSection)
    oss: OSSConfigSection = Field(default_factory=OSSConfigSection)
    email: EmailConfigSection = Field(default_factory=EmailConfigSection)
    telegram: TelegramConfigSection = Field(
        default_factory=TelegramConfigSection
    )
    x: XConfigSection = Field(default_factory=XConfigSection)

    @classmethod
    def load(cls, path: str | Path = FILE_PATH) -> 'Config':
        # file path
        path = Path(path)

        # create default config if not exists
        if not path.exists():
            config = cls()
            config.save(path)
            return config

        # load config
        data = yaml.safe_load(path.read_text('utf-8')) or {}
        config = cls.model_validate(data)

        # write back if config file is missing any fields
        if data != config.model_dump():
            config.save(path)

        # validate config
        config.validate()

        # return
        return config

    def save(self, path: str | Path = FILE_PATH) -> None:
        path = Path(path)

        # create config dir if not exists
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        # save config
        path.write_text(
            yaml.safe_dump(
                self.model_dump(),
                sort_keys=False,
                allow_unicode=True
            ),
            encoding='utf-8'
        )

    def validate(self) -> None:
        # check digest dependencies
        if self.telegram.enabled and not self.digest.enabled:
            raise ValueError('Telegram requires digest.enabled to be true')
        if self.x.enabled and not self.digest.enabled:
            raise ValueError('X requires digest.enabled to be true')

    def log(self, logger: Logger) -> None:
        def log_enabled(name: str, enabled: bool) -> None:
            logger.info(f"{name} {'enabled' if enabled else 'disabled'}")

        # log digest config
        log_enabled("Digest", self.digest.enabled)
        if self.digest.enabled:
            logger.info(f"Digest model: {self.digest.model}")

        # log oss config
        log_enabled("OSS", self.oss.enabled)

        # log email config
        log_enabled("Email", self.email.enabled)
        if self.email.enabled:
            logger.info("Email recipients:")
            for recipient in self.email.recipients:
                logger.info(f"  - {recipient}")

        # log telegram config
        log_enabled("Telegram", self.telegram.enabled)

        # log x config
        log_enabled("X", self.x.enabled)
