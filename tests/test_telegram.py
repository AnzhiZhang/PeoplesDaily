import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import InputFile

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
            images={'intro': '简短导读。'},
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
        image_paths=[Path('/issue/images/01-frontpage.png'),
                     Path('/issue/images/02-highlights.png')],
        dir_path='/issue',
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
        self.assertTrue(toc.startswith('*[第一版](https://paper.test/page)*'))
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

    def test_long_digest_keeps_all_paragraphs_for_discussion(self):
        daily = make_daily()
        paragraphs = ['甲' * 2000, '乙' * 2000, '丙' * 2000]
        daily.data.digest.highlights[0]['paragraphs'] = paragraphs
        full = build_digest_message(daily)
        self.assertGreater(len(full), MAX_MESSAGE_LEN)
        for paragraph in paragraphs:
            self.assertIn(paragraph, full)
        with patch(
            'src.send_telegram.send_messages', new_callable=AsyncMock
        ) as send:
            send_telegram(Config(), daily)
        caption, images, chunks, *_ = send.call_args.args
        self.assertLessEqual(len(caption), 1024)
        self.assertTrue(all(len(chunk) <= MAX_MESSAGE_LEN for chunk in chunks))
        for paragraph in paragraphs:
            self.assertIn(paragraph, '\n'.join(chunks))

    def test_send_marks_status_and_skips_repeats(self):
        daily = make_daily()
        with patch(
            'src.send_telegram.send_messages', new_callable=AsyncMock
        ) as send:
            send_telegram(Config(), daily)
            send_telegram(Config(), daily)
            send.assert_awaited_once()
            self.assertEqual(
                send.call_args.args[0],
                build_digest_message(daily).split("\n\n")[0] + "\n\n简短导读。",
            )
            self.assertEqual(send.call_args.args[1], [
                Path('/issue/images/01-frontpage.png'),
                Path('/issue/images/02-highlights.png')
            ])
            self.assertEqual(
                send.call_args.args[2],
                [build_digest_message(daily), *build_messages(daily)],
            )
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
    async def test_one_album_with_digest_and_toc_as_replies(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        images = [Path(directory) / f'{index}.png' for index in range(3)]
        for path in images:
            path.write_bytes(b'image')
        app = MagicMock()
        app.bot.send_media_group = AsyncMock(
            return_value=[
                SimpleNamespace(message_id=12),
                SimpleNamespace(message_id=13),
                SimpleNamespace(message_id=14),
            ]
        )
        app.bot.send_message = AsyncMock()
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
            await send_messages(
                '导读',
                images,
                ['完整摘要', '目录一', '目录二'],
                'token',
                -1,
                -2,
            )
            forward.assert_awaited_once_with(app, -2, 12)
        app.bot.send_media_group.assert_awaited_once()
        album = app.bot.send_media_group.call_args.kwargs
        self.assertEqual(album['chat_id'], -1)
        self.assertEqual(len(album['media']), 3)
        self.assertEqual(album['media'][0].caption, '导读')
        for item, path in zip(album['media'], images):
            self.assertIsInstance(item.media, InputFile)
            self.assertEqual(item.media.filename, path.name)
            self.assertEqual(item.media.input_file_content, path.read_bytes())
        self.assertTrue(
            all(item.caption is None for item in album['media'][1:])
        )
        calls = app.bot.send_message.await_args_list
        self.assertEqual(len(calls), 3)
        for call, text in zip(calls, ['完整摘要', '目录一', '目录二']):
            self.assertEqual(call.kwargs['chat_id'], -2)
            self.assertEqual(call.kwargs['reply_to_message_id'], 34)
            self.assertEqual(call.kwargs['text'], text)
