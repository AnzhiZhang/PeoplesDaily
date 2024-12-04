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
            is_cname: bool,
            region: str,
            pretty_endpoint: str | None,
    ):
        self.enabled = enabled
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.is_cname = is_cname
        self.region = region
        self.pretty_endpoint = pretty_endpoint

    def __repr__(self):
        return (
            f'{self.__class__.__name__}('
            f'enabled={self.enabled!r}, '
            f'access_key_id={self.access_key_id!r}, '
            f'access_key_secret={self.access_key_secret!r}, '
            f'endpoint={self.endpoint!r}, '
            f'bucket_name={self.bucket_name!r}'
            f'is_cname={self.is_cname!r}'
            f'region={self.region!r}'
            f'pretty_endpoint={self.pretty_endpoint!r}'
            f')'
        )


def join_oss_key(date: str, name: str) -> str:
    path = '/'.join(date.split('-'))
    return f'{path}/{name}'


def upload_to_oss(
        oss_config: OSSConfig,
        today_peoples_daily: TodayPeopleDaily
):
    # construct oss bucket
    auth = oss2.AuthV4(oss_config.access_key_id, oss_config.access_key_secret)
    bucket = oss2.Bucket(
        auth,
        oss_config.endpoint,
        oss_config.bucket_name,
        is_cname=oss_config.is_cname,
        region=oss_config.region
    )

    # upload to oss
    merged_pdf_key = join_oss_key(
        today_peoples_daily.date_str,
        today_peoples_daily.merged_pdf_name
    )
    bucket.put_object_from_file(
        join_oss_key(
            today_peoples_daily.date_str,
            today_peoples_daily.pages_zip_name
        ),
        today_peoples_daily.pages_zip_path
    )
    bucket.put_object_from_file(
        merged_pdf_key,
        today_peoples_daily.merged_pdf_path
    )
    bucket.put_object_from_file(
        join_oss_key(
            today_peoples_daily.date_str,
            today_peoples_daily.data_json_name
        ),
        today_peoples_daily.data_json_path
    )

    # set oss merged pdf url
    if oss_config.pretty_endpoint is not None:
        endpoint = oss_config.pretty_endpoint
    else:
        endpoint = oss_config.endpoint
    today_peoples_daily.set_oss_url(f'{endpoint}/{merged_pdf_key}')
