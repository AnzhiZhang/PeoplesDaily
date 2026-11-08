import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from PIL import Image, ImageChops
from pydantic import ValidationError

from src.config import Config
from src.data import Data, DigestDataSection, XDataSection
from src.send_x import (
    XAPIError,
    XCards,
    XClient,
    XDigest,
    XDraw,
    XMetric,
    _create_x_images,
    build_post,
    generate_x_digest,
    send_x,
    validate_metric,
    validate_sources,
    verify_emphasis,
    weighted_length,
)
from src.status import Status

VALID = {
    'post': '今日关注政策与国际合作的新进展。',
    'highlights': [
        {
            'source_id': 1,
            'title': '一项重要进展',
            'body': '保留原摘要中的关键事实。',
        }
    ],
    'commentary': [],
}


def commentary(emphasis=None, source_id=1, body='评论认为要打通改革堵点。'):
    return {
        'source_id': source_id,
        'title': '改革激发活力',
        'body': body,
        'emphasis': emphasis,
    }


def response(status, data):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    return result


class XGenerationTests(unittest.TestCase):
    def test_numbers_and_chinese_have_the_same_visual_center(self):
        daily = SimpleNamespace(data=Data(date='2026-11-07'), pages=[])
        font = XCards(daily, 2).font(40)
        image = Image.new('RGB', (500, 200), 'white')
        draw = XDraw(image)
        draw.text((10, 10), '国123', font=font, fill='black')
        boundary = 20 + round(font.font_variant(size=80).getlength('国'))
        mask = ImageChops.invert(image.convert('L'))
        chinese = mask.crop((20, 0, boundary, 200)).getbbox()
        digits = mask.crop((boundary, 0, 500, 200)).getbbox()
        self.assertIsNotNone(chinese)
        self.assertIsNotNone(digits)
        self.assertLessEqual(
            abs((chinese[1] + chinese[3]) / 2 - (digits[1] + digits[3]) / 2), 1
        )

    def test_limits_and_link_free_copy(self):
        for value in ('字' * 101, '访问 example.com', '第一行\n第二行'):
            payload = copy.deepcopy(VALID)
            payload['post'] = value
            with self.assertRaises(ValidationError):
                XDigest.model_validate(payload)
        payload = copy.deepcopy(VALID)
        payload['highlights'][0]['body'] = '字' * 81
        with self.assertRaises(ValidationError):
            XDigest.model_validate(payload)
        self.assertEqual(weighted_length('中文abc'), 7)
        post = build_post('2026-11-07', 8, XDigest.model_validate(VALID))
        self.assertEqual(
            post,
            '人民日报今日速读｜2026年11月07日 · 星期六 · 今日8版\n\n'
            + VALID['post']
        )
        self.assertLessEqual(weighted_length(post), 280)

    def test_source_ids_are_unique_and_present(self):
        original = DigestDataSection.model_validate(
            {'highlights': [{}], 'commentary': [{}]}
        )
        payload = copy.deepcopy(VALID)
        payload['commentary'] = [commentary(), commentary()]
        with self.assertRaises(ValueError):
            validate_sources(XDigest.model_validate(payload), original)
        payload['commentary'] = [commentary(source_id=2)]
        with self.assertRaises(ValueError):
            validate_sources(XDigest.model_validate(payload), original)
        payload['commentary'] = []
        payload['highlights'] *= 2
        with self.assertRaises(ValueError):
            validate_sources(XDigest.model_validate(payload), original)

    def test_saved_digest_is_reused_and_post_is_saved(self):
        daily = SimpleNamespace(
            data=Data(
                date='2026-11-07',
                page_count=8,
                digest={'highlights': [{}], 'commentary': []},
                x=XDataSection(),
            ),
            logger=MagicMock(),
        )
        original = copy.deepcopy(daily.data.digest)
        config = Config.model_validate(
            {'digest': {'api_key': 'test', 'model': 'test'}}
        )
        with (
            patch('src.send_x.OpenAI') as client,
            patch('src.send_x.commentary_context', return_value={}),
        ):
            api = client.return_value.__enter__.return_value
            response = api.chat.completions.create.return_value
            response.choices = [
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(VALID))
                )
            ]
            response.usage = None
            one = generate_x_digest(config, daily)
            self.assertEqual(one, generate_x_digest(config, daily))
            self.assertEqual(client.call_count, 1)
        self.assertEqual(daily.data.x.digest, VALID)
        self.assertEqual(
            daily.data.x.post,
            build_post(daily.data.date, daily.data.page_count, one),
        )
        self.assertEqual(original, daily.data.digest)

    def test_two_commentaries_need_concise_copy(self):
        payload = copy.deepcopy(VALID)
        payload['commentary'] = [
            commentary(body='字' * 71),
            commentary(source_id=2),
        ]
        with self.assertRaises(ValidationError):
            XDigest.model_validate(payload)
        payload['commentary'] = [
            commentary(),
            commentary(source_id=2),
            commentary(source_id=3),
        ]
        with self.assertRaises(ValidationError):
            XDigest.model_validate(payload)
        payload['commentary'] = [
            commentary({'kind': 'claim', 'text': '字' * 31}),
            commentary(source_id=2),
        ]
        with self.assertRaises(ValidationError):
            XDigest.model_validate(payload)

    def test_quote_and_data_verification_is_source_specific(self):
        metric = XMetric(
            value='4,142', label='参展企业', source_quote='4142家境外企业参展'
        )
        validate_metric(metric, '本届共有4142家境外企业参展。')
        with self.assertRaises(ValueError):
            validate_metric(metric, '其他来源')
        metric.value = '414'
        with self.assertRaises(ValueError):
            validate_metric(metric, '4142家境外企业参展')
        payload = copy.deepcopy(VALID)
        payload['commentary'] = [
            commentary({'kind': 'quote', 'text': '以改革打通堵点'}),
            commentary(
                {'kind': 'data', 'metrics': [metric.model_dump()]}, source_id=2
            ),
        ]
        result = XDigest.model_validate(payload)
        verify_emphasis(
            result,
            {1: '文章认为应以改革打通堵点。', 2: '4142家境外企业参展'},
            MagicMock(),
        )
        self.assertIsNotNone(result.commentary[0].emphasis)
        self.assertIsNone(result.commentary[1].emphasis)
        verify_emphasis(result, {2: '以改革打通堵点'}, MagicMock())
        self.assertIsNone(result.commentary[0].emphasis)

    def test_all_emphasis_layouts_single_and_double(self):
        options = [
            None,
            {'kind': 'claim', 'text': '字' * 30},
            {'kind': 'quote', 'text': '字' * 30},
            {
                'kind': 'data',
                'metrics': [
                    {
                        'value': '超过1234万元',
                        'label': '字' * 14,
                        'source_quote': '原文',
                    }
                ],
            },
        ]
        sources = [{'url': 'source'}]
        daily = SimpleNamespace(
            data=Data(
                date='2026-11-07',
                page_count=8,
                digest={
                    'highlights': [{'sources': sources}] * 3,
                    'commentary': [
                        {'title': '原文（人民时评）', 'url': 'source'}
                    ]
                    * 2,
                },
            ),
            pages=[
                SimpleNamespace(
                    articles=[SimpleNamespace(url='source')], page='01'
                )
            ],
        )
        cards = XCards(daily, 3)
        with tempfile.TemporaryDirectory() as directory:
            for count in (1, 2):
                for emphasis in options:
                    payload = copy.deepcopy(VALID)
                    payload['commentary'] = [
                        commentary(
                            emphasis, i + 1, '字' * (100 if count == 1 else 70)
                        )
                        for i in range(count)
                    ]
                    for item in payload['commentary']:
                        item['title'] = '字' * 20
                    cards.commentary(
                        XDigest.model_validate(payload),
                        Path(directory) / 'commentary.png',
                    )
            digest = XDigest.model_validate(VALID)
            digest.highlights[0].body = '字' * 80
            cards.highlights(digest, Path(directory) / 'highlights.png')
        self.assertEqual(XCards.column_tag('观点（和音）'), '和音')
        self.assertEqual(XCards.column_tag('普通标题'), '')

    def test_rendered_images_and_saved_post_match_digest(self):
        import pymupdf

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            pdf_path = path / 'issue.pdf'
            with pymupdf.open() as pdf:
                page = pdf.new_page(width=600, height=900)
                page.draw_rect(page.rect, color=(1, 0, 0), fill=(1, 0, 0))
                pdf.save(pdf_path)
            daily = SimpleNamespace(
                data=Data(date='2026-11-07', page_count=8),
                merged_pdf_path=str(pdf_path),
                pages=[],
            )
            cards = XCards(daily, 3)
            cards.frontpage(path / 'card.png')
            with Image.open(path / 'card.png') as image:
                self.assertEqual(image.size, (2400, 3200))
                r, g, b = image.getpixel((1200, 1600))
                self.assertGreater(r, 240)
                self.assertLess(g, 10)
                self.assertLess(b, 10)
            daily.dir_path = str(path)
            daily.logger = MagicMock()
            daily.data.digest = DigestDataSection.model_validate(
                {'highlights': [{'sources': []}], 'commentary': []}
            )
            daily.data.x = XDataSection(digest=copy.deepcopy(VALID))
            output = _create_x_images(Config(), daily)
            self.assertEqual(
                {file.name for file in output},
                {'01-frontpage.png', '02-highlights.png'},
            )
            self.assertEqual(
                daily.data.x.post,
                build_post(
                    daily.data.date, daily.data.page_count,
                    XDigest.model_validate(VALID),
                ),
            )


class XPublishTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.issue = self.root / '2026/11/07'
        self.images_dir = self.issue / 'x'
        self.images_dir.mkdir(parents=True)
        render = patch(
            'src.send_x._create_x_images',
            return_value=[
                self.images_dir / '01-frontpage.png',
                self.images_dir / '02-highlights.png',
            ],
        )
        self.render = render.start()
        self.addCleanup(render.stop)
        self.config = Config.model_validate(
            {
                'x': {
                    'client_id': 'test-client',
                    'client_secret': 'test-secret',
                    'refresh_token': 'test-refresh',
                    'username': 'dailyreader',
                }
            }
        )
        self.token_path = self.root / 'x_token.json'
        self.token_path.write_text(
            json.dumps(
                {
                    'client_id': 'test-client',
                    'access_token': 'test-token',
                    'refresh_token': 'test-refresh',
                    'expires_at': time.time() + 7200,
                }
            )
        )
        self.daily = SimpleNamespace(
            data=Data(
                date='2026-11-07',
                page_count=8,
                x=XDataSection(
                    digest=VALID,
                    post=build_post(
                        '2026-11-07', 8, XDigest.model_validate(VALID)
                    ),
                ),
            ),
            dir_path=str(self.issue),
            status=Status(),
            logger=MagicMock(),
        )
        for name in ('01-frontpage.png', '02-highlights.png'):
            Image.new('RGB', (10, 10), 'white').save(self.images_dir / name)

    def client(self, mock):
        client = mock.return_value.__enter__.return_value
        client.account.return_value = {'id': '42', 'username': 'dailyreader'}
        client.upload_image.side_effect = ['101', '102']
        client.publish.return_value = '12345'
        return client

    def test_publish_updates_id_and_skips_repeats(self):
        with patch('src.send_x.XClient') as mock:
            client = self.client(mock)

            def publish(text, media_ids):
                self.assertEqual(media_ids, ['101', '102'])
                self.assertIn('人民日报今日速读｜2026年11月07日', text)
                return '12345'

            client.publish.side_effect = publish
            self.assertEqual(
                send_x(self.config, self.daily), 'https://x.com/i/status/12345'
            )
            self.assertEqual(
                send_x(self.config, self.daily), 'https://x.com/i/status/12345'
            )
            self.render.assert_called_once_with(self.config, self.daily)
            self.assertEqual(client.publish.call_count, 1)
            self.assertEqual(client.upload_image.call_count, 2)
        self.assertEqual(self.daily.status.x_post_id, '12345')

    def test_upload_failure_does_not_publish(self):
        with patch('src.send_x.XClient') as mock:
            client = self.client(mock)
            client.upload_image.side_effect = XAPIError('upload failed', 403)
            with self.assertRaises(XAPIError):
                send_x(self.config, self.daily)
            client.publish.assert_not_called()
        self.assertIsNone(self.daily.status.x_post_id)

    def test_missing_credentials_and_wrong_account(self):
        with self.assertRaisesRegex(ValueError, 'Missing X credentials'):
            XClient(Config().x)
        with patch('src.send_x.requests.Session') as session:
            session.return_value.request.return_value.status_code = 200
            session.return_value.request.return_value.json.return_value = {
                'data': {'id': '42', 'username': 'someone_else'}
            }
            with XClient(self.config.x, self.token_path) as client:
                with self.assertRaisesRegex(ValueError, 'account mismatch'):
                    client.account()

    def test_v2_upload_and_create_payloads_and_no_redirects(self):
        with patch('src.send_x.requests.Session') as session:
            response = session.return_value.request.return_value
            response.status_code = 200
            response.json.side_effect = [
                {'data': {'id': '101'}},
                {'data': {'id': '12345'}},
            ]
            with XClient(self.config.x, self.token_path) as client:
                self.assertEqual(
                    client.upload_image(self.images_dir / '01-frontpage.png'),
                    '101',
                )
                self.assertEqual(client.publish('text', ['101']), '12345')
            calls = session.return_value.request.call_args_list
            self.assertEqual(
                calls[0].args, ('POST', 'https://api.x.com/2/media/upload')
            )
            self.assertEqual(
                calls[0].kwargs['data'], {'media_category': 'tweet_image'}
            )
            self.assertEqual(
                calls[1].kwargs['json'],
                {'text': 'text', 'media': {'media_ids': ['101']}},
            )
            self.assertFalse(calls[1].kwargs['allow_redirects'])

    def test_http_error_redacts_credentials(self):
        with patch('src.send_x.requests.Session') as session:
            response = session.return_value.request.return_value
            response.status_code = 403
            response.json.return_value = {
                'detail': 'denied test-token test-secret test-refresh'
            }
            with XClient(self.config.x, self.token_path) as client:
                with self.assertRaises(XAPIError) as error:
                    client.account()
        self.assertNotIn('test-', str(error.exception))
        self.assertNotIn('test-secret', repr(self.config))


class XOAuth2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.token_path = self.root / 'data/x_token.json'
        self.token_path.parent.mkdir()
        self.cached = {
            'client_id': 'client-id',
            'access_token': 'old-access',
            'refresh_token': 'old-refresh',
            'expires_at': time.time() + 7200,
        }
        self.token_path.write_text(json.dumps(self.cached))
        self.data = {
            'x': {
                'client_id': 'client-id',
                'client_secret': 'client-secret',
                'refresh_token': 'old-refresh',
                'username': 'reader',
            }
        }
        self.config = Config.model_validate(self.data)
        self.tokens = {
            'token_type': 'bearer',
            'expires_in': 7200,
            'access_token': 'new-access',
            'refresh_token': 'new-refresh',
        }
        self.account = response(
            200, {'data': {'id': '42', 'username': 'reader'}}
        )
        self.session = self.enterContext(
            patch('src.send_x.requests.Session')
        ).return_value
        self.refresh = self.enterContext(patch('src.send_x.requests.post'))
        self.refresh.return_value = response(200, self.tokens)

    def test_valid_cached_token_is_reused(self):
        self.session.request.return_value = response(
            200, {'data': {'id': '123'}}
        )
        with XClient(self.config.x, self.token_path) as client:
            self.assertEqual(client.publish('text', ['101']), '123')
        self.session.headers.update.assert_any_call(
            {'Authorization': 'Bearer old-access'}
        )
        self.refresh.assert_not_called()

    def test_401_refreshes_and_persists_rotated_tokens(self):
        self.session.request.side_effect = [response(401, {}), self.account]
        with XClient(self.config.x, self.token_path) as client:
            client.account()
        self.assertEqual(self.refresh.call_count, 1)
        self.assertEqual(
            self.refresh.call_args.args, ('https://api.x.com/2/oauth2/token',)
        )
        self.assertEqual(
            self.refresh.call_args.kwargs['auth'],
            ('client-id', 'client-secret'),
        )
        self.assertEqual(
            self.refresh.call_args.kwargs['data']['grant_type'], 'refresh_token'
        )
        self.assertEqual(
            self.refresh.call_args.kwargs['data']['refresh_token'],
            'old-refresh',
        )
        self.session.headers.update.assert_any_call(
            {'Authorization': 'Bearer new-access'}
        )
        saved = json.loads(self.token_path.read_text())
        self.assertEqual(saved['access_token'], 'new-access')
        self.assertEqual(saved['refresh_token'], 'new-refresh')
        self.assertGreater(saved['expires_at'], time.time() + 7000)
        self.assertEqual(self.token_path.stat().st_mode & 0o777, 0o600)

    def test_401_refresh_rewinds_image_stream(self):
        image = self.root / 'image.png'
        image.write_bytes(b'complete-image')
        seen = []

        def upload(*args, **kwargs):
            stream = kwargs['files']['media'][1]
            seen.append(stream.read())
            return (
                response(401, {})
                if len(seen) == 1
                else response(200, {'data': {'id': '101'}})
            )

        self.session.request.side_effect = upload
        with XClient(self.config.x, self.token_path) as client:
            self.assertEqual(client.upload_image(image), '101')
        self.assertEqual(self.refresh.call_count, 1)
        self.assertEqual(seen, [b'complete-image', b'complete-image'])

    def test_second_401_is_not_retried_again(self):
        self.session.request.return_value = response(
            401, {'detail': 'unauthorized'}
        )
        with XClient(self.config.x, self.token_path) as client:
            with self.assertRaises(XAPIError):
                client.account()
        self.assertEqual(self.session.request.call_count, 2)
        self.assertEqual(self.refresh.call_count, 1)

    def test_public_client_refresh_uses_client_id_without_secret(self):
        self.data['x']['client_secret'] = ''
        self.config = Config.model_validate(self.data)
        self.session.request.side_effect = [response(401, {}), self.account]
        with XClient(self.config.x, self.token_path) as client:
            client.account()
        self.assertIsNone(self.refresh.call_args.kwargs['auth'])
        self.assertEqual(
            self.refresh.call_args.kwargs['data']['client_id'], 'client-id'
        )

    def test_refresh_rejection_preserves_file_and_redacts_token(self):
        cached = self.token_path.read_text()
        self.refresh.return_value = response(
            400,
            {
                'error': 'invalid_grant',
                'error_description': 'invalid old-refresh client-secret',
            },
        )
        self.session.request.return_value = response(401, {})
        with XClient(self.config.x, self.token_path) as client:
            with self.assertRaises(XAPIError) as error:
                client.account()
        self.assertEqual(self.session.request.call_count, 1)
        self.assertEqual(self.refresh.call_count, 1)
        self.assertEqual(self.token_path.read_text(), cached)
        self.assertNotIn('old-refresh', str(error.exception))
        self.assertNotIn('client-secret', str(error.exception))

    def test_refresh_before_request_with_missing_expiring_or_rotated_tokens(
        self,
    ):
        for state in ('missing', 'expiring', 'rotated'):
            with self.subTest(state=state):
                self.refresh.reset_mock()
                self.session.reset_mock()
                cached = dict(self.cached)
                expected_refresh = 'old-refresh'
                if state == 'missing':
                    self.token_path.unlink()
                else:
                    cached['expires_at'] = time.time() + 30
                    if state == 'rotated':
                        cached.update(
                            refresh_token='rotated-refresh', expires_at=1
                        )
                        expected_refresh = 'rotated-refresh'
                    self.token_path.write_text(json.dumps(cached))
                self.session.request.return_value = self.account
                with XClient(self.config.x, self.token_path) as client:
                    client.account()
                self.refresh.assert_called_once()
                self.assertEqual(
                    self.refresh.call_args.kwargs['data']['refresh_token'],
                    expected_refresh,
                )
                self.assertEqual(self.session.request.call_count, 1)
                self.session.headers.update.assert_any_call(
                    {'Authorization': 'Bearer new-access'}
                )
                saved = json.loads(self.token_path.read_text())
                self.assertEqual(saved['access_token'], 'new-access')
                self.assertEqual(saved['refresh_token'], 'new-refresh')

    def test_corrupt_cache_stops_before_refresh(self):
        self.token_path.write_text('{broken')
        with self.assertRaisesRegex(XAPIError, 'Could not read'):
            XClient(self.config.x, self.token_path)
        self.refresh.assert_not_called()

    def test_invalid_refresh_response_does_not_overwrite_tokens(self):
        cached = self.token_path.read_text()
        self.refresh.return_value = response(200, {'access_token': 'bad'})
        self.session.request.return_value = response(401, {})
        with XClient(self.config.x, self.token_path) as client:
            with self.assertRaises(XAPIError):
                client.account()
        self.assertEqual(self.token_path.read_text(), cached)

    def test_token_write_failure_prevents_retrying_api_request(self):
        cached = self.token_path.read_text()
        with patch('src.send_x.Path.replace', side_effect=OSError('disk full')):
            self.session.request.return_value = response(401, {})
            with XClient(self.config.x, self.token_path) as client:
                with self.assertRaisesRegex(XAPIError, 'Could not save'):
                    client.account()
            self.assertEqual(self.session.request.call_count, 1)
        self.assertEqual(self.token_path.read_text(), cached)
