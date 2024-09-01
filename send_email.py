import os
import smtplib
import argparse
import datetime

import markdown2

from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr, formataddr

from main import TodayPeopleDaily

__all__ = [
    'EmailConfig',
    'send_email',
]

DAY_OF_WEEK = ['一', '二', '三', '四', '五', '六', '日']


class EmailConfig:
    def __init__(
            self,
            smtp_server: str,
            smtp_port: int,
            smtp_ssl: bool,
            smtp_user: str,
            smtp_password: str,
            sender: str,
            recipients: list[str]
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_ssl = smtp_ssl
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender = sender
        self.recipients = recipients

    @property
    def enabled(self):
        return len(self.recipients) != 0


def format_addr(s):
    name, addr = parseaddr(s)
    return formataddr((name, addr))


def send_email(
        config: EmailConfig,
        today_peoples_daily: TodayPeopleDaily
):
    # connect smtp server
    if config.smtp_ssl:
        server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port)
    else:
        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
    server.login(config.smtp_user, config.smtp_password)

    # get date
    date = datetime.datetime.strptime(today_peoples_daily.date, '%Y-%m-%d')

    # construct email
    msg = MIMEMultipart()
    msg['From'] = format_addr(config.sender)
    msg['Subject'] = Header(
        (
            f'人民日报 '
            f'{date.year}年{str(date.month).zfill(2)}月'
            f'{str(date.day).zfill(2)}日 '
            f'星期{DAY_OF_WEEK[date.weekday()]}'
        ),
        'utf-8'
    ).encode()
    msg.attach(MIMEText(
        markdown2.markdown(today_peoples_daily.release_body),
        'html',
        'utf-8'
    ))

    # attach pdf
    pdf_name = os.path.basename(today_peoples_daily.merged_file_path)
    with open(today_peoples_daily.merged_file_path, 'rb') as f:
        mime = MIMEBase(
            'application',
            'pdf',
            filename=pdf_name
        )
        mime.add_header(
            'Content-Disposition',
            'attachment',
            filename=pdf_name
        )
        mime.add_header('Content-ID', '<0>')
        mime.add_header('X-Attachment-Id', '0')
        mime.set_payload(f.read())
        encoders.encode_base64(mime)
        msg.attach(mime)

    # send email
    for recipient in config.recipients:
        msg['To'] = format_addr(recipient)
        server.sendmail(config.sender, [recipient], msg.as_string())

    # quit server
    server.quit()


def main():
    # setup parser
    parser = argparse.ArgumentParser(
        description="Send People's Daily by email",
    )
    parser.add_argument(
        "--smtp-server",
        help="SMTP server",
    )
    parser.add_argument(
        "--smtp-port",
        help="SMTP port",
    )
    parser.add_argument(
        "--smtp-ssl",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="SMTP SSL",
    )
    parser.add_argument(
        "--smtp-user",
        help="SMTP user",
    )
    parser.add_argument(
        "--smtp-password",
        help="SMTP password",
    )
    parser.add_argument(
        "--sender",
        help="Sender",
    )
    parser.add_argument(
        "--recipients",
        help="Recipients",
        nargs='+',
    )

    # parse arguments
    args = parser.parse_args()
    smtp_server = args.smtp_server
    smtp_port = args.smtp_port
    smtp_ssl = args.smtp_ssl
    smtp_user = args.smtp_user
    smtp_password = args.smtp_password
    sender = args.sender
    recipients = args.recipients

    # get today peoples daily
    today_peoples_daily = TodayPeopleDaily()
    today_peoples_daily.get_today_peoples_daily()

    # send email
    send_email(
        EmailConfig(
            smtp_server,
            smtp_port,
            smtp_ssl,
            smtp_user,
            smtp_password,
            sender,
            recipients
        ),
        today_peoples_daily
    )


if __name__ == '__main__':
    main()
