import oss2

from .peoples_daily import TodayPeopleDaily

__all__ = [
    'OSSConfig',
    'upload_to_oss',
]


class OSSConfig:
    def __init__(
            self,
            enabled: bool,
            access_key_id: str,
            access_key_secret: str,
            endpoint: str,
            bucket_name: str,
    ):
        self.enabled = enabled
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name

    def __repr__(self):
        return (
            f'{self.__class__.__name__}('
            f'enabled={self.enabled!r}, '
            f'access_key_id={self.access_key_id!r}, '
            f'access_key_secret={self.access_key_secret!r}, '
            f'endpoint={self.endpoint!r}, '
            f'bucket_name={self.bucket_name!r}'
            f')'
        )


def upload_to_oss(
        oss_config: OSSConfig,
        today_peoples_daily: TodayPeopleDaily
):
    # construct oss bucket
    auth = oss2.Auth(oss_config.access_key_id, oss_config.access_key_secret)
    bucket = oss2.Bucket(
        auth,
        oss_config.endpoint,
        oss_config.bucket_name
    )

    # upload to oss
    bucket.put_object_from_file(
        f'{today_peoples_daily.date}/{today_peoples_daily.pages_zip_name}',
        today_peoples_daily.pages_zip_path
    )
    bucket.put_object_from_file(
        f'{today_peoples_daily.date}/{today_peoples_daily.merged_pdf_name}',
        today_peoples_daily.merged_pdf_path
    )
    bucket.put_object_from_file(
        f'{today_peoples_daily.date}/{today_peoples_daily.data_json_name}',
        today_peoples_daily.data_json_path
    )
