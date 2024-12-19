import os
import uuid
import argparse
import datetime
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from func_timeout import func_timeout, FunctionTimedOut

from src.exceptions import NoPagesFoundError
from src.logger import Logger
from src.peoples_daily import TodayPeopleDaily
from src.send_email import EmailConfig, send_email
from src.upload_to_oss import OSSConfig, upload_to_oss

logger = Logger("People's Daily")


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
        help="Specific date in format 'YYYY-MM-DD'",
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
    parser.add_argument(
        "--oss-pretty-endpoint",
        default=None,
        help="OSS pretty endpoint",
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
        args.oss_region,
        args.oss_pretty_endpoint
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
    oss_pretty_endpoint = os.environ.get('OSS_PRETTY_ENDPOINT', None)
    oss_config = OSSConfig(
        oss_enabled,
        oss_access_key_id,
        oss_access_key_secret,
        oss_endpoint,
        oss_bucket_name,
        oss_is_cname,
        oss_region,
        oss_pretty_endpoint
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


def log_config(oss_config: OSSConfig, email_config: EmailConfig):
    # log oss config
    if oss_config.enabled:
        logger.info(f"OSS enabled")
    else:
        logger.info("OSS disabled")

    # log email config
    if email_config.enabled:
        logger.info("Email enabled")
        logger.info("Email recipients:")
        for recipient in email_config.recipients:
            logger.info(f"  - {recipient}")
    else:
        logger.info("Email disabled")


def daily_task(
        oss_config: OSSConfig,
        email_config: EmailConfig,
        date: datetime.date = None,
        retry: bool = False
) -> TodayPeopleDaily | None:
    # retry
    def retry_func() -> None:
        if retry:
            logger.warning(f"retry in 30 minutes...")
            thread = threading.Timer(
                60 * 30,
                daily_task,
                args=(oss_config, email_config),
                kwargs={'date': date, 'retry': retry}
            )
            thread.name = f"retry-{today_peoples_daily.date_str}"
            thread.start()
        else:
            raise e

    # init today peoples daily
    today_peoples_daily = TodayPeopleDaily(logger, date)

    # main task
    try:
        # get today peoples daily
        logger.info(
            f"Getting People's Daily for {today_peoples_daily.date_str}..."
        )
        func_timeout(60 * 10, today_peoples_daily.get_today_peoples_daily)
        logger.info(f"Got People's Daily for {today_peoples_daily.date_str}")

        # upload to oss
        if oss_config.enabled:
            upload_to_oss(oss_config, today_peoples_daily)
            logger.info(
                f"Uploaded to OSS at {today_peoples_daily.oss_merged_pdf_url}"
            )

        # send email
        if email_config.enabled:
            send_email(
                email_config,
                today_peoples_daily
            )
            logger.info(f"Sent email to {email_config.recipients}")

        # return
        return today_peoples_daily
    except NoPagesFoundError as e:
        logger.warning(f"No pages found for {today_peoples_daily.date_str}")
        return retry_func()
    except FunctionTimedOut:
        logger.warning(f"Timed out for {today_peoples_daily.date_str}")
        return retry_func()
    except Exception as e:
        logger.exception("Unknown error occurred", exc_info=e)
        return retry_func()


def main_once(args, oss_config: OSSConfig, email_config: EmailConfig):
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


def main_cron(oss_config: OSSConfig, email_config: EmailConfig):
    # build scheduler
    scheduler = BackgroundScheduler(timezone=datetime.UTC)

    # Beijing time is UTC+8
    scheduler.add_job(
        daily_task,
        'cron',
        hour='22',
        minute='0',
        args=(oss_config, email_config),
        kwargs={'retry': True}
    )

    # start scheduler
    scheduler.start()

    # command line
    logger.info(
        'Enter "exit" to exit, '
        '"get <YYYY-MM-DD>" to get People\'s Daily of the day'
    )
    while True:
        text = input()
        if text == 'exit':
            scheduler.shutdown()
            break
        elif text == 'threads':
            logger.info(f'Totally {len(threading.enumerate())} threads:')
            for thread in threading.enumerate():
                logger.info(f'  - {thread.name}: {thread}')
        elif text.startswith('get '):
            date = datetime.date.fromisoformat(text[4:])
            daily_task(oss_config, email_config, date)


def main():
    # parse args
    parser = build_arg_parser()
    args = parser.parse_args()

    # run
    if args.cron_enabled:
        oss_config, email_config = read_config_from_env()
        log_config(oss_config, email_config)
        main_cron(oss_config, email_config)
    else:
        oss_config, email_config = read_config_from_args(args)
        log_config(oss_config, email_config)
        main_once(args, oss_config, email_config)


if __name__ == '__main__':
    main()
