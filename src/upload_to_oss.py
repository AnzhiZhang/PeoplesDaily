import oss2

from .config import Config
from .peoples_daily import TodayPeopleDaily

__all__ = [
    'upload_to_oss',
]


def join_oss_key(date: str, name: str) -> str:
    path = '/'.join(date.split('-'))
    return f'{path}/{name}'


def upload_to_oss(
        config: Config,
        today_peoples_daily: TodayPeopleDaily
):
    # construct oss bucket
    auth = oss2.AuthV4(config.oss.access_key_id, config.oss.access_key_secret)
    bucket = oss2.Bucket(
        auth,
        config.oss.endpoint,
        config.oss.bucket_name,
        is_cname=config.oss.is_cname,
        region=config.oss.region
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
    if config.oss.pretty_endpoint is not None:
        endpoint = config.oss.pretty_endpoint
    else:
        endpoint = config.oss.endpoint
    today_peoples_daily.set_oss_url(f'{endpoint}/{merged_pdf_key}')
