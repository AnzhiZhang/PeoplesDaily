import os
import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from peoples_daily import TodayPeopleDaily
from send_email import EmailConfig, send_email


def get_today_peoples_daily(email_config: EmailConfig):
    # get today peoples daily
    today_peoples_daily = TodayPeopleDaily()
    today_peoples_daily.get_today_peoples_daily()
    print(f"Got People's Daily for {today_peoples_daily.date}")

    # send email
    if email_config.enabled:
        send_email(
            email_config,
            today_peoples_daily
        )
        print(f"Sent email to {email_config.recipients}")


def main():
    # email config
    smtp_port = int(os.environ.get('SMTP_PORT', 0))
    smtp_ssl = os.environ.get('SMTP_SSL', 'False').lower() == 'true'
    recipients = os.environ.get('RECIPIENTS', '').split(",")
    recipients = [r.strip() for r in recipients if r.strip() != '']
    email_config = EmailConfig(
        os.environ.get('SMTP_SERVER', ''),
        smtp_port,
        smtp_ssl,
        os.environ.get('SMTP_USER', ''),
        os.environ.get('SMTP_PASSWORD', ''),
        os.environ.get('SENDER', ''),
        recipients
    )

    # log email config
    if email_config.enabled:
        print(f"Email enabled with recipients: {email_config.recipients}")

    # build scheduler
    scheduler = BlockingScheduler(timezone=datetime.UTC)
    scheduler.add_job(
        get_today_peoples_daily,
        'cron',
        hour='0',
        minute='0',
        args=(email_config,)
    )

    # start scheduler
    scheduler.start()


if __name__ == '__main__':
    main()
