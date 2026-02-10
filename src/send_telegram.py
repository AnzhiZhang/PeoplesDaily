import asyncio
import time
from pathlib import Path

from telegram import InputFile
from telegram.constants import ParseMode
from telegram.ext import Application
from telegram.helpers import escape_markdown

from .config import Config
from .peoples_daily import Page, TodayPeopleDaily

__all__ = [
    'send_telegram',
]

MAX_MESSAGE_LEN = 3900


def esc(text: str) -> str:
    return escape_markdown(text, version=2)


def build_header(daily: TodayPeopleDaily) -> str:
    return f"*[{esc(daily.date_str)}]({daily.home_url})*\n\n今日 {daily.page_count} 版"


def build_page_section(page: Page) -> str:
    lines = [f"*[{esc(page.title)}]({page.html_url})*", ""]
    for article in page.articles:
        lines.append(f"  \\- [{esc(article.title)}]({article.url})")
    return "\n".join(lines)


def split_message(text: str, max_len: int = MAX_MESSAGE_LEN) -> list[str]:
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    buf: list[str] = []
    buf_len = 0

    for line in text.splitlines(keepends=True):
        if len(line) > max_len:
            if buf:
                parts.append("".join(buf).rstrip("\n"))
                buf, buf_len = [], 0
            for i in range(0, len(line), max_len):
                parts.append(line[i: i + max_len].rstrip("\n"))
            continue

        if buf_len + len(line) > max_len and buf:
            parts.append("".join(buf).rstrip("\n"))
            buf, buf_len = [line], len(line)
        else:
            buf.append(line)
            buf_len += len(line)

    if buf:
        parts.append("".join(buf).rstrip("\n"))

    return [p for p in parts if p.strip()]


def build_messages(daily: TodayPeopleDaily) -> list[str]:
    sections = [build_header(daily)]
    for page in daily.pages:
        sections.append(build_page_section(page))

    # merge small sections
    merged: list[str] = []
    buf, buf_len = [], 0
    for section in sections:
        if not section.strip():
            continue
        candidate = ("\n\n" if buf else "") + section
        if buf_len + len(candidate) > MAX_MESSAGE_LEN:
            merged.append("".join(buf))
            buf, buf_len = [section], len(section)
        else:
            buf.append(candidate)
            buf_len += len(candidate)
    if buf:
        merged.append("".join(buf))

    # split long messages
    chunks: list[str] = []
    for text in merged:
        chunks.extend(split_message(text))

    return chunks


async def wait_for_forward(
        app: Application,
        discussion_chat_id: int,
        not_before_ts: float,
        timeout: float = 12.0,
) -> int:
    """Wait for channel message to be auto-forwarded to discussion group."""
    offset: int | None = None
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        updates = await app.bot.get_updates(
            offset=offset, timeout=1, allowed_updates=["message"]
        )
        for upd in updates:
            offset = upd.update_id + 1
            msg = upd.message
            if not msg or msg.chat.id != discussion_chat_id:
                continue

            msg_ts = getattr(msg, "date", None)
            if msg_ts is not None and msg_ts.timestamp() < not_before_ts:
                continue

            if getattr(msg, "is_automatic_forward", False):
                return msg.message_id

        await asyncio.sleep(0.4)

    raise RuntimeError("Timeout waiting for auto-forward message")


async def send_messages(
        chunks: list[str],
        pdf_path: Path,
        token: str,
        channel_id: int,
        discussion_chat_id: int,
) -> None:
    if not chunks:
        return

    app = Application.builder().token(token).build()
    async with app:
        # send main message to channel
        channel_msg = await app.bot.send_message(
            chat_id=channel_id,
            text=chunks[0],
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )

        # wait for auto-forward to discussion group
        forward_id = await wait_for_forward(
            app, discussion_chat_id, channel_msg.date.timestamp()
        )

        # send replies to discussion group
        for chunk in chunks[1:]:
            await app.bot.send_message(
                chat_id=discussion_chat_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_to_message_id=forward_id,
                disable_web_page_preview=True,
            )

        # send pdf to discussion group
        with pdf_path.open("rb") as f:
            await app.bot.send_document(
                chat_id=discussion_chat_id,
                document=InputFile(f, filename=pdf_path.name),
                reply_to_message_id=forward_id,
            )


def send_telegram(
        config: Config,
        today_peoples_daily: TodayPeopleDaily
) -> None:
    pdf_path = Path(today_peoples_daily.merged_pdf_path)
    if not pdf_path.exists():
        today_peoples_daily.logger.warning(f"PDF not found: {pdf_path}")
        return

    chunks = build_messages(today_peoples_daily)
    asyncio.run(send_messages(
        chunks,
        pdf_path,
        config.telegram.bot_token,
        config.telegram.channel_id,
        config.telegram.discussion_chat_id,
    ))
