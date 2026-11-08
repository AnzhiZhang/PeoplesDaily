import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import Config
from src.data import Data
from src.send_telegram import (
    MAX_MESSAGE_LEN,
    build_digest_message,
    build_messages,
    send_messages,
    send_telegram,
)
from src.status import Status


def make_daily():
    return SimpleNamespace(
        data=Data(
            date='2026-11-08',
            page_count=8,
            digest={
                'highlights': [
                    {
                        'title': '今日要点标题',
                        'paragraphs': ['摘要正文。'],
                        'sources': [{'url': 'https://paper.test/article'}],
                    }
                ],
                'commentary': [],
            },
        ),
        home_url='https://paper.test/page',
        pages=[
            SimpleNamespace(
                title='第一版',
                html_url='https://paper.test/page',
                articles=[
                    SimpleNamespace(
                        title='完整目录文章', url='https://paper.test/article'
                    )
                ],
            )
        ],
        status=Status(),
        logger=MagicMock(),
    )


class TelegramTests(unittest.TestCase):
    def test_digest_header_and_toc_are_separate(self):
        daily = make_daily()
        digest = build_digest_message(daily)
        self.assertEqual(
            digest.splitlines()[0],
            '*[2026年11月08日](https://paper.test/page) 星期日｜今日8版*',
        )
        self.assertNotIn('AI 摘要', digest)
        self.assertIn('摘要正文。', digest)
        self.assertNotIn('完整目录文章', digest)
        toc = '\n\n'.join(build_messages(daily))
        self.assertTrue(
            toc.startswith('*[第一版](https://paper.test/page)*')
        )
        self.assertNotIn('今日目录', toc)
        self.assertIn('完整目录文章', toc)
        self.assertNotIn('摘要正文。', toc)

    def test_long_toc_preserves_every_article(self):
        daily = make_daily()
        daily.pages[0].articles = [
            SimpleNamespace(
                title=f'新闻{index}' + '字' * 80,
                url=f'https://paper.test/article/{index}',
            )
            for index in range(100)
        ]
        chunks = build_messages(daily)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= MAX_MESSAGE_LEN for chunk in chunks))
        toc = '\n'.join(chunks)
        for article in daily.pages[0].articles:
            self.assertIn(f']({article.url})', toc)

    def test_send_marks_status_and_skips_repeats(self):
        daily = make_daily()
        with patch(
            'src.send_telegram.send_messages', new_callable=AsyncMock
        ) as send:
            send_telegram(Config(), daily)
            send_telegram(Config(), daily)
            send.assert_awaited_once()
            self.assertEqual(
                send.call_args.args[0], build_digest_message(daily)
            )
            self.assertEqual(send.call_args.args[1], build_messages(daily))
        self.assertTrue(daily.status.telegram_sent)

    def test_reply_failure_does_not_mark_sent(self):
        daily = make_daily()
        with patch(
            'src.send_telegram.send_messages', new_callable=AsyncMock
        ) as send:
            send.side_effect = RuntimeError('reply failed')
            with self.assertRaisesRegex(RuntimeError, 'reply failed'):
                send_telegram(Config(), daily)
        self.assertFalse(daily.status.telegram_sent)


class TelegramDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_channel_digest_with_all_toc_chunks_as_replies(self):
        app = MagicMock()
        app.bot.send_message = AsyncMock(
            return_value=SimpleNamespace(message_id=12)
        )
        with (
            patch('src.send_telegram.Application') as factory,
            patch(
                'src.send_telegram.wait_for_forward',
                new_callable=AsyncMock,
                return_value=34,
            ) as forward,
        ):
            builder = factory.builder.return_value.token.return_value
            builder.build.return_value = app
            await send_messages('摘要', ['目录一', '目录二'], 'token', -1, -2)
            forward.assert_awaited_once_with(app, -2, 12)
        calls = app.bot.send_message.await_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0].kwargs['chat_id'], -1)
        self.assertEqual(calls[0].kwargs['text'], '摘要')
        self.assertNotIn('reply_to_message_id', calls[0].kwargs)
        for call, text in zip(calls[1:], ['目录一', '目录二']):
            self.assertEqual(call.kwargs['chat_id'], -2)
            self.assertEqual(call.kwargs['reply_to_message_id'], 34)
            self.assertEqual(call.kwargs['text'], text)
