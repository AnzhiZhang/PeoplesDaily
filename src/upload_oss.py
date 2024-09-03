import argparse

import oss2

from peoples_daily import TodayPeopleDaily

__all__ = [
    'OSSConfig',
    'upload_to_oss',
]


class OSSConfig:
    def __init__(
            self,
            access_key_id: str,
            access_key_secret: str,
            endpoint: str,
            bucket_name: str,
    ):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name

    @property
    def enabled(self):
        return self.access_key_id != ''


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


def main():
    # setup parser
    parser = argparse.ArgumentParser(
        description="Upload People's Daily to OSS",
    )
    parser.add_argument(
        "--oss-access-key-id",
        help="OSS access key ID",
    )
    parser.add_argument(
        "--oss-access-key-secret",
        help="OSS access key secret",
    )
    parser.add_argument(
        "--oss-endpoint",
        help="OSS endpoint",
    )
    parser.add_argument(
        "--oss-bucket-name",
        help="OSS bucket name",
    )

    # parse arguments
    args = parser.parse_args()
    oss_access_key_id = args.oss_access_key_id
    oss_access_key_secret = args.oss_access_key_secret
    oss_endpoint = args.oss_endpoint
    oss_bucket_name = args.oss_bucket_name

    # get today peoples daily
    today_peoples_daily = TodayPeopleDaily()
    today_peoples_daily.get_today_peoples_daily()

    # upload to oss
    upload_to_oss(
        OSSConfig(
            oss_access_key_id,
            oss_access_key_secret,
            oss_endpoint,
            oss_bucket_name
        ),
        today_peoples_daily
    )

    # log
    print(f"Uploaded to OSS for {today_peoples_daily.date}")


if __name__ == '__main__':
    main()
