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


def build_highlight(highlight: dict) -> str:
    # source links in parentheses after title
    sources = highlight['sources']
    if len(sources) == 1:
        links = f"[原文]({sources[0]['url']})"
    else:
        links = " · ".join(
            f"[原文 {n}]({s['url']})" for n, s in enumerate(sources, start=1)
        )

    blocks = [f"*{esc(highlight['title'])}* \\({links}\\)"]
    blocks.extend(esc(p) for p in highlight['paragraphs'])

    return "\n\n".join(blocks)


def build_digest_message(daily: TodayPeopleDaily) -> str:
    digest = daily.digest
    header = f"*[{esc(daily.date_str)}]({daily.home_url}) — AI 摘要*"

    # build sections as blocks
    sections: list[tuple[str, list[str]]] = []
    highlights = [build_highlight(h) for h in digest['highlights']]
    sections.append(("*今日要点*", highlights))
    commentary = [
        f"*[{esc(c['title'])}]({c['url']})*\n{esc(c['point'])}"
        for c in digest['commentary']
    ]
    if commentary:
        sections.append(("*评论风向*", commentary))

    # append blocks until message length limit
    text = header
    for title, items in sections:
        candidate = f"{text}\n\n{title}"
        added = False
        for item in items:
            if len(candidate) + len(item) + 2 > MAX_MESSAGE_LEN:
                break
            candidate += f"\n\n{item}"
            added = True
        if not added:
            break
        text = candidate

    return text


async def wait_for_forward(
        app: Application,
        discussion_chat_id: int,
        channel_message_id: int,
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

            # match the forward of exactly this channel message
            origin = getattr(msg, "forward_origin", None)
            if (
                    getattr(msg, "is_automatic_forward", False)
                    and getattr(origin, "message_id", None) == channel_message_id
            ):
                return msg.message_id

        await asyncio.sleep(0.4)

    raise RuntimeError("Timeout waiting for auto-forward message")


async def send_messages(
        chunks: list[str],
        digest_text: str | None,
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
            app, discussion_chat_id, channel_msg.message_id
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

        # # send pdf to discussion group
        # with pdf_path.open("rb") as f:
        #     await app.bot.send_document(
        #         chat_id=discussion_chat_id,
        #         document=InputFile(f, filename=pdf_path.name),
        #         reply_to_message_id=forward_id,
        #     )

        # send digest to channel
        if digest_text is not None:
            await app.bot.send_message(
                chat_id=channel_id,
                text=digest_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True,
            )


def send_telegram(
        config: Config,
        today_peoples_daily: TodayPeopleDaily
) -> None:
    # skip if already sent
    if today_peoples_daily.status.telegram_sent:
        today_peoples_daily.logger.info('Telegram send skipped (already done)')
        return

    # check pdf exists
    pdf_path = Path(today_peoples_daily.merged_pdf_path)
    if not pdf_path.exists():
        today_peoples_daily.logger.warning(f"PDF not found: {pdf_path}")
        return

    # build and send messages
    chunks = build_messages(today_peoples_daily)
    digest_text = None
    if today_peoples_daily.digest is not None:
        digest_text = build_digest_message(today_peoples_daily)
    asyncio.run(send_messages(
        chunks,
        digest_text,
        pdf_path,
        config.telegram.bot_token,
        config.telegram.channel_id,
        config.telegram.discussion_chat_id,
    ))

    # persist status
    today_peoples_daily.status.telegram_sent = True
    today_peoples_daily.save_status()

    # log
    today_peoples_daily.logger.info('Sent to Telegram')
