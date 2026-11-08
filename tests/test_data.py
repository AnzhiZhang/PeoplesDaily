import datetime
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.config import Config
from src.data import Data, DigestDataSection, XDataSection
from src.digest import generate_digest
from src.peoples_daily import Article, Page, TodayPeopleDaily
from src.send_telegram import build_digest_message


class DataTests(unittest.TestCase):
    def test_save_and_restore_preserves_digest_x_and_status(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch('src.peoples_daily.DATA_DIR', directory),
        ):
            daily = TodayPeopleDaily(MagicMock(), datetime.date(2026, 11, 7))
            daily.data.page_count = 8
            daily.pages = [
                Page.from_data(
                    daily,
                    '01',
                    {
                        'title': '第一版',
                        'html_url': 'https://paper.test/page',
                        'articles': [
                            {
                                'title': '新闻',
                                'url': 'https://paper.test/article',
                            }
                        ],
                    },
                )
            ]
            daily.data.pages = {
                page.page: page.to_data() for page in daily.pages
            }
            daily.data.digest = DigestDataSection.model_validate(
                {'highlights': [{'title': '要点'}]}
            )
            daily.data.x = XDataSection(
                digest={
                    'commentary': [{'title': '评论一'}, {'title': '评论二'}]
                },
                post='今日配文',
            )
            daily.status.downloaded = True
            daily.status.x_post_id = '12345'
            daily.save()
            cached = json.loads(Path(daily.data_json_path).read_text())
            cached.update(
                pages_zip_path='/old/issue.zip',
                merged_pdf_path='/old/issue.pdf',
                summary='old cached summary',
            )
            Path(daily.data_json_path).write_text(json.dumps(cached))
            restored = TodayPeopleDaily(MagicMock(), daily.date)
            with patch('src.peoples_daily.requests.get') as request:
                restored.get_today_peoples_daily()
                request.assert_not_called()
            self.assertEqual(restored.data, daily.data)
            self.assertEqual(
                restored.data.summary,
                '# [2026-11-07](https://paper.test/page)\n\n今日 8 版\n\n'
                '## [第一版](https://paper.test/page)\n\n'
                '- [新闻](https://paper.test/article)',
            )
            self.assertIsInstance(restored.pages[0], Page)
            self.assertIsInstance(restored.pages[0].articles[0], Article)
            self.assertEqual(
                restored.pages[0].to_data(), restored.data.pages['01']
            )
            self.assertEqual(restored.status.x_post_id, '12345')
            self.assertTrue(restored.merged_pdf_path.endswith('2026-11-07.pdf'))
            self.assertNotEqual(restored.merged_pdf_path, '/old/issue.pdf')
            restored.save()
            saved = json.loads(Path(restored.data_json_path).read_text())
            self.assertNotIn('pages_zip_path', saved)
            self.assertNotIn('merged_pdf_path', saved)
            self.assertNotIn('summary', saved)
            self.assertEqual(
                Data.load(restored.data_json_path).pages['01']['articles'][0][
                    'title'
                ],
                '新闻',
            )

    def test_digest_generation_and_telegram_read_shared_data(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch('src.peoples_daily.DATA_DIR', directory),
        ):
            daily = TodayPeopleDaily(MagicMock(), datetime.date(2026, 11, 7))
            daily.data.page_count = 1
            daily.pages = [
                Page.from_data(
                    daily,
                    '01',
                    {
                        'title': '第一版',
                        'html_url': 'https://paper.test/page',
                        'articles': [
                            {
                                'title': '原文标题',
                                'url': 'https://paper.test/article',
                            }
                        ],
                    },
                )
            ]
            daily.data.pages = {
                page.page: page.to_data() for page in daily.pages
            }
            result = {
                'highlights': [
                    {
                        'article_ids': [1],
                        'title': '摘要标题',
                        'paragraphs': ['摘要正文'],
                    }
                ],
                'commentary': [],
            }
            with (
                patch('src.digest.OpenAI') as factory,
                patch('src.digest.requests.get') as fetch,
            ):
                response = (
                    factory.return_value.chat.completions.create.return_value
                )
                response.choices = [
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(result))
                    )
                ]
                response.usage = SimpleNamespace(
                    prompt_tokens=10, completion_tokens=10
                )
                fetch.return_value.content = (
                    '<div id="ozoom"><p>新闻正文。</p></div>'.encode()
                )
                generate_digest(Config(), daily)
            self.assertIsInstance(daily.data.digest, DigestDataSection)
            self.assertEqual(
                daily.data.digest.highlights[0]['sources'][0]['title'],
                '原文标题',
            )
            self.assertTrue(daily.status.digest_generated)
            self.assertIn('摘要标题', build_digest_message(daily))

    def test_failed_write_preserves_previous_data_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            previous = '{"previous": true}'
            path.write_text(previous)
            data = Data(date='2026-11-07', page_count='8')
            with patch('src.data.json.dump', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    data.save(str(path))
            self.assertEqual(path.read_text(), previous)

    def test_failed_cache_restore_clears_downloaded_before_redownload(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch('src.peoples_daily.DATA_DIR', directory),
        ):
            daily = TodayPeopleDaily(MagicMock(), datetime.date(2026, 11, 7))
            daily.status.downloaded = True
            Path(daily.data_json_path).write_text('{broken')
            with patch(
                'src.peoples_daily.requests.get',
                side_effect=RuntimeError('offline'),
            ):
                with self.assertRaisesRegex(RuntimeError, 'offline'):
                    daily.get_today_peoples_daily()
            self.assertFalse(daily.status.downloaded)
            self.assertEqual(Path(daily.data_json_path).read_text(), '{broken')
