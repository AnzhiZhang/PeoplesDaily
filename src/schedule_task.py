import os
import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from peoples_daily import TodayPeopleDaily
from send_email import EmailConfig, send_email
from upload_oss import OSSConfig, upload_to_oss


def rcon_task(oss_config: OSSConfig, email_config: EmailConfig):
    # get today peoples daily
    today_peoples_daily = TodayPeopleDaily()
    today_peoples_daily.get_today_peoples_daily()
    print(f"Got People's Daily for {today_peoples_daily.date}")

    # upload to oss
    if oss_config.enabled:
        upload_to_oss(oss_config, today_peoples_daily)
        print("Uploaded to OSS")

    # send email
    if email_config.enabled:
        send_email(
            email_config,
            today_peoples_daily
        )
        print(f"Sent email to {email_config.recipients}")


def main():
    # oss config
    access_key_id = os.environ.get('OSS_ACCESS_KEY_ID', '')
    access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET', '')
    endpoint = os.environ.get('OSS_ENDPOINT', '')
    bucket_name = os.environ.get('OSS_BUCKET_NAME', '')
    oss_config = OSSConfig(
        access_key_id,
        access_key_secret,
        endpoint,
        bucket_name
    )

    # log oss config
    if oss_config.enabled:
        print("OSS enabled")
    else:
        print("OSS disabled")

    # email config
    smtp_port = int(os.environ.get('SMTP_PORT', 0))
    smtp_ssl = os.environ.get('SMTP_SSL', 'False').lower() == 'true'
    recipients = os.environ.get('RECIPIENTS', '').split(",")
    recipients = [r.strip() for r in recipients if r.strip() != '']
    with_attachment = os.environ.get(
        'WITH_ATTACHMENT',
        'False'
    ).lower() == 'true'
    email_config = EmailConfig(
        os.environ.get('SMTP_SERVER', ''),
        smtp_port,
        smtp_ssl,
        os.environ.get('SMTP_USER', ''),
        os.environ.get('SMTP_PASSWORD', ''),
        os.environ.get('SENDER', ''),
        recipients,
        with_attachment,
    )

    # log email config
    if email_config.enabled:
        print(f"Email enabled with recipients: {email_config.recipients}")
    else:
        print("Email disabled")

    # build scheduler
    scheduler = BlockingScheduler(timezone=datetime.UTC)
    scheduler.add_job(
        rcon_task,
        'cron',
        hour='22',
        minute='0',
        args=(oss_config, email_config)
    )

    # start scheduler
    scheduler.start()


if __name__ == '__main__':
    main()
