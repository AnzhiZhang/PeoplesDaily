import sys
import datetime
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait

from apscheduler.schedulers.background import BackgroundScheduler
from func_timeout import func_timeout, FunctionTimedOut

from src.config import Config
from src.digest import generate_digest
from src.exceptions import NoPagesFoundError
from src.logger import Logger
from src.peoples_daily import TodayPeopleDaily
from src.send_email import send_email
from src.send_telegram import send_telegram_digest, send_telegram_toc
from src.send_x import send_x
from src.upload_to_oss import upload_to_oss

logger = Logger("People's Daily")
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="peoplesdaily")


def run_after(
        task,
        config: Config,
        today_peoples_daily: TodayPeopleDaily,
        *dependencies: Future | None
):
    # propagate dependency failures before running the task
    for dependency in dependencies:
        if dependency is not None:
            dependency.result()
    return task(config, today_peoples_daily)


def daily_task(
        config: Config,
        date: datetime.date = None,
        retry: bool = False
) -> TodayPeopleDaily | None:
    # schedule retry only once per run
    retry_lock = threading.Lock()
    retry_scheduled = False

    # schedule retry
    def schedule_retry() -> None:
        # skip if already scheduled
        nonlocal retry_scheduled
        with retry_lock:
            if retry_scheduled:
                return
            retry_scheduled = True

        # start retry timer
        logger.warning(f"retry in 30 minutes...")
        thread = threading.Timer(
            60 * 30,
            daily_task,
            args=(config,),
            kwargs={'date': date, 'retry': retry}
        )
        thread.name = f"retry-{today_peoples_daily.data.date}"
        thread.start()

    # retry
    def retry_func(e: BaseException) -> None:
        if retry:
            schedule_retry()
        else:
            raise e

    # init today peoples daily
    today_peoples_daily = TodayPeopleDaily(logger, date)
    tasks = []
    digest = None
    oss = None
    telegram_toc = None

    # main task
    try:
        # get today peoples daily
        logger.info(
            f"Getting People's Daily for {today_peoples_daily.data.date}..."
        )
        func_timeout(60 * 10, today_peoples_daily.get_today_peoples_daily)

        # generate digest
        if config.digest.enabled:
            digest = executor.submit(generate_digest, config, today_peoples_daily)
            tasks.append(digest)

        # upload to oss
        if config.oss.enabled:
            oss = executor.submit(upload_to_oss, config, today_peoples_daily)
            tasks.append(oss)

        # send telegram toc
        if config.telegram.enabled:
            telegram_toc = executor.submit(
                send_telegram_toc, config, today_peoples_daily
            )
            tasks.append(telegram_toc)

        # send email after oss upload
        if config.email.enabled:
            tasks.append(executor.submit(
                run_after, send_email, config, today_peoples_daily, oss
            ))

        # send telegram digest after digest generation and toc
        if config.telegram.enabled:
            tasks.append(executor.submit(
                run_after, send_telegram_digest, config, today_peoples_daily,
                digest, telegram_toc
            ))

        # send x after digest generation
        if config.x.enabled:
            tasks.append(executor.submit(
                run_after, send_x, config, today_peoples_daily, digest
            ))

        # wait for all tasks and propagate failures
        wait(tasks)
        for task in tasks:
            task.result()

        # return
        return today_peoples_daily
    except NoPagesFoundError as e:
        logger.warning(f"No pages found for {today_peoples_daily.data.date}")
        return retry_func(e)
    except FunctionTimedOut as e:
        logger.warning(f"Timed out for {today_peoples_daily.data.date}")
        return retry_func(e)
    except Exception as e:
        logger.exception("Unknown error occurred", exc_info=e)
        return retry_func(e)
    finally:
        # save progress after all workers finish, including failed runs
        wait(tasks)
        if today_peoples_daily.status.downloaded:
            today_peoples_daily.save()


def main_once(config: Config, date: datetime.date) -> None:
    # run task
    daily_task(config, date)


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
    config = Config.load()
    logger.set_debug(config.debug)
    config.log(logger)

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
