from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

FILE_PATH = 'config/config.yaml'


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


class Config(BaseModel):
    cron_enabled: bool = False
    write_github_output: bool = False

    oss: OSSConfigSection = Field(default_factory=OSSConfigSection)
    email: EmailConfigSection = Field(default_factory=EmailConfigSection)


def load_config() -> Config:
    """
    Load config from the config file.
    :return: Config.
    """
    # file path
    path = Path(FILE_PATH)

    # create config dir if not exists
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    # write config if not exists
    if not path.exists():
        config = Config()
        path.write_text(
            yaml.safe_dump(
                config.model_dump(),
                sort_keys=False,
                allow_unicode=True
            ),
            encoding='utf-8'
        )
        return config

    # load config
    data = yaml.safe_load(path.read_text('utf-8')) or {}
    config = Config.model_validate(data)

    # return
    return config
