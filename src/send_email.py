import ssl
import smtplib
import datetime
import urllib.parse
from smtplib import SMTPDataError

import markdown2

from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr, formataddr

from .peoples_daily import TodayPeopleDaily

__all__ = [
    'EmailConfig',
    'send_email',
]

UNSUBSCRIBE_SUBJECT = "[People's Daily] Unsubscribe"
UNSUBSCRIBE_BODY = (
    "Hi Admin,\n\n"
    "I would like to unsubscribe from the daily People's Daily email. Please remove my email from the mailing list.\n\n"
    "Thank you."
)
DAY_OF_WEEK = ['一', '二', '三', '四', '五', '六', '日']


class EmailConfig:
    def __init__(
            self,
            enabled: bool,
            smtp_server: str,
            smtp_port: int,
            smtp_use_ssl: bool,
            smtp_user: str,
            smtp_password: str,
            sender: str,
            recipients: list[str],
            with_attachment: bool = False,
            unsubscribe_link_enabled: bool = False,
            unsubscribe_link_address: str = None,
    ):
        self.enabled = enabled
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_use_ssl = smtp_use_ssl
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender = sender
        self.recipients = recipients
        self.with_attachment = with_attachment
        self.unsubscribe_link_enabled = unsubscribe_link_enabled
        self.unsubscribe_link_address = unsubscribe_link_address

    def __repr__(self):
        return (
            f'{self.__class__.__name__}('
            f'enabled={self.enabled!r}, '
            f'smtp_server={self.smtp_server!r}, '
            f'smtp_port={self.smtp_port!r}, '
            f'smtp_use_ssl={self.smtp_use_ssl!r}, '
            f'smtp_user={self.smtp_user!r}, '
            f'smtp_password={self.smtp_password!r}, '
            f'sender={self.sender!r}, '
            f'recipients={self.recipients!r}, '
            f'with_attachment={self.with_attachment!r}, '
            f'unsubscribe_link_enabled={self.unsubscribe_link_enabled!r}, '
            f'unsubscribe_link_address={self.unsubscribe_link_address!r}'
            f')'
        )


def format_addr(s):
    name, addr = parseaddr(s)
    return formataddr((name, addr))


def get_unsubscribe_link(address: str) -> str:
    params = {
        "subject": UNSUBSCRIBE_SUBJECT,
        "body": UNSUBSCRIBE_BODY
    }
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"mailto:{address}?{query}"


def send_email(
        config: EmailConfig,
        today_peoples_daily: TodayPeopleDaily
):
    # connect smtp server
    if config.smtp_use_ssl:
        server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port)
    else:
        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        context = ssl.create_default_context()
        server.starttls(context=context)

    # login
    server.login(config.smtp_user, config.smtp_password)

    # get date
    date = datetime.datetime.strptime(today_peoples_daily.date_str, '%Y-%m-%d')

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

    # add oss paragraph
    if today_peoples_daily.oss_merged_pdf_url is not None:
        oss_paragraph = markdown2.markdown(
            f'[在线阅读 PDF]({today_peoples_daily.oss_merged_pdf_url})'
        )
        msg.attach(MIMEText(oss_paragraph, 'html', 'utf-8'))

    # add table of contents
    msg.attach(MIMEText(
        markdown2.markdown(today_peoples_daily.release_body),
        'html',
        'utf-8'
    ))

    # add unsubscribe link
    if config.unsubscribe_link_enabled:
        link = get_unsubscribe_link(config.unsubscribe_link_address)
        unsubscribe_paragraph = markdown2.markdown(f'[Unsubscribe]({link})')
        msg.attach(MIMEText(unsubscribe_paragraph, 'html', 'utf-8'))

    # attach pdf
    if config.with_attachment:
        with open(today_peoples_daily.merged_pdf_path, 'rb') as f:
            mime = MIMEBase(
                'application',
                'pdf',
                filename=today_peoples_daily.merged_pdf_name
            )
            mime.add_header(
                'Content-Disposition',
                'attachment',
                filename=today_peoples_daily.merged_pdf_name
            )
            mime.add_header('Content-ID', '<0>')
            mime.add_header('X-Attachment-Id', '0')
            mime.set_payload(f.read())
            encoders.encode_base64(mime)
            msg.attach(mime)

    # send email
    msg['To'] = format_addr(config.sender)
    for recipient in config.recipients:
        msg.replace_header('To', format_addr(recipient))
        try:
            server.sendmail(config.sender, [recipient], msg.as_string())
        except SMTPDataError as error:
            today_peoples_daily.logger.warning(
                f'Failed to send email to {recipient}',
                exc_info=error
            )

    # quit server
    server.quit()
