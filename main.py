import os
import sys
import uuid
import datetime
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from func_timeout import func_timeout, FunctionTimedOut

from src.config import Config, load_config
from src.exceptions import NoPagesFoundError
from src.logger import Logger
from src.peoples_daily import TodayPeopleDaily
from src.send_email import send_email
from src.send_telegram import send_telegram
from src.upload_to_oss import upload_to_oss

logger = Logger("People's Daily")


def write_multiline_output(fh, name, value):
    delimiter = uuid.uuid4()
    print(f'{name}<<{delimiter}', file=fh)
    print(value, file=fh)
    print(delimiter, file=fh)


def log_config(config: Config) -> None:
    # log oss config
    if config.oss.enabled:
        logger.info(f"OSS enabled")
    else:
        logger.info("OSS disabled")

    # log email config
    if config.email.enabled:
        logger.info("Email enabled")
        logger.info("Email recipients:")
        for recipient in config.email.recipients:
            logger.info(f"  - {recipient}")
    else:
        logger.info("Email disabled")

    # log telegram config
    if config.telegram.enabled:
        logger.info("Telegram enabled")
    else:
        logger.info("Telegram disabled")


def daily_task(
        config: Config,
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
                args=(config,),
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
        if config.oss.enabled:
            upload_to_oss(config, today_peoples_daily)
            logger.info(
                f"Uploaded to OSS at {today_peoples_daily.oss_merged_pdf_url}"
            )

        # send email
        if config.email.enabled:
            send_email(
                config,
                today_peoples_daily
            )
            logger.info(f"Sent email to {config.email.recipients}")

        # send telegram
        if config.telegram.enabled:
            send_telegram(
                config,
                today_peoples_daily
            )
            logger.info("Sent to Telegram")

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


def main_once(config: Config, date: datetime.date) -> None:
    # run task
    today_peoples_daily = daily_task(config, date)

    # set output
    # DEPRECATED: GitHub Actions output is deprecated, will be removed in the future.
    if config.write_github_output:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            for name, value in today_peoples_daily.data.items():
                if '\n' in value:
                    write_multiline_output(fh, name, value)
                else:
                    print(f'{name}={value}', file=fh)


def main_cron(config: Config) -> None:
    # build scheduler
    scheduler = BackgroundScheduler(timezone=datetime.UTC)

    # Beijing time is UTC+8
    scheduler.add_job(
        daily_task,
        'cron',
        hour='22',
        minute='0',
        args=(config,),
        kwargs={'retry': True}
    )

    # start scheduler
    scheduler.start()

    # command line
    logger.info(
        'Enter "exit" to exit, '
        '"get YYYY-MM-DD" to get People\'s Daily of the day'
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
            daily_task(config, date=date)


def main():
    # load config
    config = load_config()
    log_config(config)

    # run
    if config.cron_enabled:
        main_cron(config)
    else:
        # read date from command line, format in YYYY-MM-DD
        # use today if not provided
        date_str = sys.argv[1] if len(sys.argv) > 1 else None
        date = datetime.date.fromisoformat(date_str) if date_str else None

        # run once
        main_once(config, date=date)


if __name__ == '__main__':
    main()
