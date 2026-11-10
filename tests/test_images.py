import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image, ImageChops
from pydantic import ValidationError

from src.config import Config
from src.data import Data, DigestDataSection, ImagesDataSection
from src.generate_images import (
    ImageDigest,
    ImageCanvas,
    ImageMetric,
    ImageRenderer,
    generate_image_digest,
    generate_images,
    validate_metric,
    validate_item_counts,
    verify_emphasis,
)

VALID = {
    'intro': '今日关注政策与国际合作的新进展。',
    'highlights': [
        {
            'title': '一项重要进展',
            'body': '保留原摘要中的关键事实。',
        }
    ],
    'commentary': [],
}


def commentary(emphasis=None, body='评论认为要打通改革堵点。'):
    return {
        'title': '改革激发活力',
        'body': body,
        'emphasis': emphasis,
    }


class ImageGenerationTests(unittest.TestCase):
    def test_numbers_and_chinese_have_the_same_visual_center(self):
        daily = SimpleNamespace(data=Data(date='2026-11-07'), pages=[])
        font = ImageRenderer(daily, 2).font(40)
        image = Image.new('RGB', (500, 200), 'white')
        draw = ImageCanvas(image)
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
            payload['intro'] = value
            with self.assertRaises(ValidationError):
                ImageDigest.model_validate(payload)
        payload = copy.deepcopy(VALID)
        payload['highlights'][0]['body'] = '字' * 81
        with self.assertRaises(ValidationError):
            ImageDigest.model_validate(payload)

    def test_image_items_must_match_full_digest_counts(self):
        original = DigestDataSection.model_validate(
            {'highlights': [{}], 'commentary': [{}]}
        )
        payload = copy.deepcopy(VALID)
        with self.assertRaisesRegex(ValueError, 'commentary'):
            validate_item_counts(ImageDigest.model_validate(payload), original)
        payload['commentary'] = [commentary()]
        validate_item_counts(ImageDigest.model_validate(payload), original)
        payload['commentary'].append(commentary())
        with self.assertRaisesRegex(ValueError, 'commentary'):
            validate_item_counts(ImageDigest.model_validate(payload), original)
        payload['commentary'] = [commentary()]
        payload['highlights'] *= 2
        with self.assertRaisesRegex(ValueError, 'highlights'):
            validate_item_counts(ImageDigest.model_validate(payload), original)

    def test_saved_image_digest_is_reused_without_changing_source(self):
        daily = SimpleNamespace(
            data=Data(
                date='2026-11-07',
                page_count=8,
                digest={'highlights': [{}], 'commentary': []},
            ),
            logger=MagicMock(),
        )
        original = copy.deepcopy(daily.data.digest)
        config = Config.model_validate(
            {'digest': {'api_key': 'test', 'model': 'test'}}
        )
        with (
            patch('src.generate_images.OpenAI') as client,
            patch('src.generate_images.commentary_context', return_value={}),
        ):
            api = client.return_value.__enter__.return_value
            response = api.chat.completions.create.return_value
            response.choices = [
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(VALID))
                )
            ]
            response.usage = None
            one = generate_image_digest(config, daily)
            self.assertEqual(one, generate_image_digest(config, daily))
            self.assertEqual(client.call_count, 1)
        self.assertEqual(
            daily.data.images.model_dump(), VALID
        )
        self.assertEqual(original, daily.data.digest)

    def test_generation_keeps_four_items_and_replaces_incomplete_cache(self):
        payload = copy.deepcopy(VALID)
        payload['highlights'] = [
            {'title': f'第{index}条', 'body': '对应原摘要内容。'}
            for index in range(1, 5)
        ]
        daily = SimpleNamespace(
            data=Data(
                date='2026-11-10',
                digest={'highlights': [{}] * 4, 'commentary': []},
                images=VALID,
            ),
            logger=MagicMock(),
        )
        with (
            patch('src.generate_images.OpenAI') as client,
            patch('src.generate_images.commentary_context', return_value={}),
        ):
            api = client.return_value.__enter__.return_value
            response = api.chat.completions.create.return_value
            response.choices = [SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(payload))
            )]
            response.usage = None
            result = generate_image_digest(Config(), daily)
        self.assertEqual(
            [item.title for item in result.highlights],
            ['第1条', '第2条', '第3条', '第4条']
        )
        self.assertEqual(daily.data.images.model_dump(), payload)
        api.chat.completions.create.assert_called_once()

    def test_two_commentaries_use_the_same_field_limits(self):
        payload = copy.deepcopy(VALID)
        payload['commentary'] = [
            commentary({'kind': 'claim', 'text': '字' * 40}, '字' * 100),
            commentary(body='字' * 100),
        ]
        ImageDigest.model_validate(payload)
        payload['commentary'][0]['body'] += '字'
        with self.assertRaises(ValidationError):
            ImageDigest.model_validate(payload)
        payload['commentary'] = [commentary()] * 3
        with self.assertRaises(ValidationError):
            ImageDigest.model_validate(payload)

    def test_quote_and_data_verification_is_source_specific(self):
        metric = ImageMetric(
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
                {'kind': 'data', 'metrics': [metric.model_dump()]}
            ),
        ]
        result = ImageDigest.model_validate(payload)
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
            {'kind': 'claim', 'text': '字' * 40},
            {'kind': 'quote', 'text': '字' * 40},
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
        renderer = ImageRenderer(daily, 3)
        with tempfile.TemporaryDirectory() as directory:
            for count in (1, 2):
                for emphasis in options:
                    payload = copy.deepcopy(VALID)
                    payload['commentary'] = [
                        commentary(emphasis, '字' * 100)
                        for i in range(count)
                    ]
                    for item in payload['commentary']:
                        item['title'] = '字' * 20
                    renderer.commentary(
                        ImageDigest.model_validate(payload),
                        Path(directory) / 'commentary.png',
                    )
            for count in (1, 3, 4, 5):
                payload = copy.deepcopy(VALID)
                payload['highlights'][0].update(
                    title='字' * 20, body='字' * 80
                )
                payload['highlights'] *= count
                daily.data.digest.highlights = [
                    {'sources': sources} for _ in range(count)
                ]
                renderer.highlights(
                    ImageDigest.model_validate(payload),
                    Path(directory) / 'highlights.png'
                )
        self.assertEqual(ImageRenderer.column_tag('观点（和音）'), '和音')
        self.assertEqual(ImageRenderer.column_tag('普通标题'), '')

    def test_rendered_images_match_digest(self):
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
            renderer = ImageRenderer(daily, 3)
            renderer.frontpage(path / 'image.png')
            with Image.open(path / 'image.png') as image:
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
            daily.data.images = ImagesDataSection.model_validate(VALID)
            generate_images(Config(), daily)
            output = sorted((Path(daily.dir_path) / 'images').glob('*.png'))
            self.assertEqual(
                {file.name for file in output},
                {'01-frontpage.png', '02-highlights.png'},
            )
            self.assertEqual(daily.image_paths, output)
            self.assertEqual(Path(daily.dir_path) / 'images', output[0].parent)
