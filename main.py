import os
import uuid
import argparse
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

from src.peoples_daily import TodayPeopleDaily
from src.send_email import EmailConfig, send_email
from src.upload_to_oss import OSSConfig, upload_to_oss


def write_multiline_output(fh, name, value):
    delimiter = uuid.uuid4()
    print(f'{name}<<{delimiter}', file=fh)
    print(value, file=fh)
    print(delimiter, file=fh)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Get today people's daily",
    )

    # specific date
    parser.add_argument(
        '--date',
        type=datetime.date.fromisoformat,
        help="Specific date",
    )

    # cron enabled
    parser.add_argument(
        "--cron-enabled",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="RCON enabled, the task will run daily, otherwise only run once",
    )

    # GitHub output
    parser.add_argument(
        "--write-github-output",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write GitHub output",
    )

    # oss
    parser.add_argument(
        "--oss-enabled",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="OSS enabled",
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
    parser.add_argument(
        "--oss-is-cname",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="OSS is CNAME",
    )
    parser.add_argument(
        "--oss-region",
        help="OSS region",
    )

    # email
    parser.add_argument(
        "--email-enabled",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Email enabled",
    )
    parser.add_argument(
        "--email-smtp-server",
        help="SMTP server",
    )
    parser.add_argument(
        "--email-smtp-port",
        help="SMTP port",
    )
    parser.add_argument(
        "--email-smtp-use-ssl",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="SMTP SSL",
    )
    parser.add_argument(
        "--email-smtp-user",
        help="SMTP user",
    )
    parser.add_argument(
        "--email-smtp-password",
        help="SMTP password",
    )
    parser.add_argument(
        "--email-sender",
        help="Sender",
    )
    parser.add_argument(
        "--email-recipients",
        help="Recipients",
        nargs='+',
    )
    parser.add_argument(
        "--email-with-attachment",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="With attachment",
    )
    return parser


def read_config_from_args(args) -> tuple[OSSConfig, EmailConfig]:
    # oss config
    oss_config = OSSConfig(
        args.oss_enabled,
        args.oss_access_key_id,
        args.oss_access_key_secret,
        args.oss_endpoint,
        args.oss_bucket_name,
        args.oss_is_cname,
        args.oss_region
    )

    # email config
    email_config = EmailConfig(
        args.email_enabled,
        args.email_smtp_server,
        args.email_smtp_port,
        args.email_smtp_use_ssl,
        args.email_smtp_user,
        args.email_smtp_password,
        args.email_sender,
        args.email_recipients,
        args.email_with_attachment,
    )

    # return
    return oss_config, email_config


def read_config_from_env() -> tuple[OSSConfig, EmailConfig]:
    def get_bool_env(key: str) -> bool:
        return os.environ.get(key, 'False').lower() == 'true'

    # oss config
    oss_enabled = get_bool_env('OSS_ENABLED')
    oss_access_key_id = os.environ.get('OSS_ACCESS_KEY_ID', '')
    oss_access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET', '')
    oss_endpoint = os.environ.get('OSS_ENDPOINT', '')
    oss_bucket_name = os.environ.get('OSS_BUCKET_NAME', '')
    oss_is_cname = get_bool_env('OSS_IS_CNAME')
    oss_region = os.environ.get('OSS_REGION', '')
    oss_config = OSSConfig(
        oss_enabled,
        oss_access_key_id,
        oss_access_key_secret,
        oss_endpoint,
        oss_bucket_name,
        oss_is_cname,
        oss_region
    )

    # email config
    email_enabled = get_bool_env('EMAIL_ENABLED')
    email_smtp_server = os.environ.get('EMAIL_SMTP_SERVER', '')
    email_smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', 0))
    email_smtp_use_ssl = get_bool_env('EMAIL_SMTP_USE_SSL')
    email_smtp_user = os.environ.get('EMAIL_SMTP_USER', '')
    email_smtp_password = os.environ.get('EMAIL_SMTP_PASSWORD', '')
    email_sender = os.environ.get('EMAIL_SENDER', '')
    email_recipients = [
        r.strip()
        for r in os.environ.get('EMAIL_RECIPIENTS', '').split(",")
        if r.strip() != ''
    ]
    email_with_attachment = get_bool_env('EMAIL_WITH_ATTACHMENT')
    email_config = EmailConfig(
        email_enabled,
        email_smtp_server,
        email_smtp_port,
        email_smtp_use_ssl,
        email_smtp_user,
        email_smtp_password,
        email_sender,
        email_recipients,
        email_with_attachment,
    )

    # return
    return oss_config, email_config


def daily_task(
        oss_config: OSSConfig,
        email_config: EmailConfig,
        date: datetime.date = None
) -> TodayPeopleDaily:
    # log oss config
    if oss_config.enabled:
        print(f"OSS enabled with config: {oss_config}")
    else:
        print("OSS disabled")

    # log email config
    if email_config.enabled:
        print(f"Email enabled with config: {email_config}")
        print(f"Email enabled with recipients: {email_config.recipients}")
    else:
        print("Email disabled")

    # get today peoples daily
    today_peoples_daily = TodayPeopleDaily(date)
    today_peoples_daily.get_today_peoples_daily()
    print(f"Got People's Daily for {today_peoples_daily.date}")

    # upload to oss
    if oss_config.enabled:
        upload_to_oss(oss_config, today_peoples_daily)
        print(f"Uploaded to OSS at {today_peoples_daily.oss_merged_pdf_url}")

    # send email
    if email_config.enabled:
        send_email(
            email_config,
            today_peoples_daily
        )
        print(f"Sent email to {email_config.recipients}")

    # return
    return today_peoples_daily


def main_once(args):
    # read config
    oss_config, email_config = read_config_from_args(args)

    # run task
    today_peoples_daily = daily_task(oss_config, email_config, args.date)

    # set output
    if args.write_github_output:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            for name, value in today_peoples_daily.data.items():
                if '\n' in value:
                    write_multiline_output(fh, name, value)
                else:
                    print(f'{name}={value}', file=fh)


def main_cron():
    # read config
    oss_config, email_config = read_config_from_env()

    # build scheduler
    scheduler = BlockingScheduler(timezone=datetime.UTC)
    scheduler.add_job(
        daily_task,
        'cron',
        hour='23',
        minute='0',
        args=(oss_config, email_config)
    )

    # start scheduler
    scheduler.start()


def main():
    # parse arguments
    parser = build_arg_parser()
    args = parser.parse_args()

    # run
    if args.cron_enabled:
        main_cron()
    else:
        main_once(args)


if __name__ == '__main__':
    main()
