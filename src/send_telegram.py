import asyncio
import datetime
import time
from pathlib import Path

from telegram import InputMediaPhoto
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
    date = datetime.date.fromisoformat(daily.data.date)
    weekday = '一二三四五六日'[date.weekday()]
    return (
        f"*[{date:%Y年%m月%d日}]({daily.home_url}) 星期{weekday}｜"
        f"今日{daily.data.page_count}版*"
    )


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
    sections = [build_page_section(page) for page in daily.pages]

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


def build_highlight(highlight: dict, source_pages: dict[str, str]) -> str:
    # source links in parentheses after title
    links = "、".join(
        f"[{source_pages[source['url']]}]({source['url']})"
        for source in highlight['sources']
    )

    blocks = [f"*{esc(highlight['title'])}* \\({links}\\)"]
    blocks.extend(esc(p) for p in highlight['paragraphs'])

    return "\n\n".join(blocks)


def build_digest_message(daily: TodayPeopleDaily) -> str:
    digest = daily.data.digest
    header = build_header(daily)

    # build sections as blocks
    sections: list[tuple[str, list[str]]] = []
    source_pages = {
        article.url: f'第{int(page.page):02d}版'
        for page in daily.pages
        for article in page.articles
    }
    highlights = [
        build_highlight(h, source_pages) for h in digest.highlights
    ]
    sections.append(("*今日要点*", highlights))
    commentary = [
        f"*[{esc(c['title'])}]({c['url']})*\n{esc(c['point'])}"
        for c in digest.commentary
    ]
    if commentary:
        sections.append(("*评论风向*", commentary))

    # include every digest block; split into replies when sending
    blocks = [header]
    for title, items in sections:
        if items:
            blocks.append(title)
            blocks.extend(items)
    return "\n\n".join(blocks)


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
        caption: str,
        images: list[Path],
        chunks: list[str],
        token: str,
        channel_id: int,
        discussion_chat_id: int
) -> None:
    app = Application.builder().token(token).build()
    async with app:
        # send one album with a short introduction to channel
        media = [
            InputMediaPhoto(
                path.read_bytes(), filename=path.name,
                caption=caption if index == 0 else None,
                parse_mode=ParseMode.MARKDOWN_V2 if index == 0 else None
            )
            for index, path in enumerate(images)
        ]
        messages = await app.bot.send_media_group(
            chat_id=channel_id, media=media
        )

        # wait for auto-forward to discussion group
        forward_id = await wait_for_forward(
            app, discussion_chat_id, messages[0].message_id
        )

        # send full digest and toc as replies to the album
        for chunk in chunks:
            await app.bot.send_message(
                chat_id=discussion_chat_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_to_message_id=forward_id,
                disable_web_page_preview=True
            )


def send_telegram(
        config: Config,
        today_peoples_daily: TodayPeopleDaily
) -> None:
    # skip if already sent
    if today_peoples_daily.status.telegram_sent:
        today_peoples_daily.logger.info(
            'Telegram send skipped (already done)'
        )
        return

    # build album caption and full digest with toc replies
    caption = (
        f"{build_header(today_peoples_daily)}\n\n"
        f"{esc(today_peoples_daily.data.images.intro)}"
    )
    chunks = split_message(build_digest_message(today_peoples_daily))
    chunks.extend(build_messages(today_peoples_daily))
    asyncio.run(send_messages(
        caption, today_peoples_daily.image_paths, chunks,
        config.telegram.bot_token,
        config.telegram.channel_id, config.telegram.discussion_chat_id
    ))

    # update status
    today_peoples_daily.status.telegram_sent = True

    # log
    today_peoples_daily.logger.info('Sent to Telegram')
