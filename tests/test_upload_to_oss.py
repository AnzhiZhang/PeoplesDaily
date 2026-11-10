import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from src.config import Config
from src.data import Data
from src.status import Status
from src.upload_to_oss import upload_images_to_oss, upload_to_oss


class OSSUploadTests(unittest.TestCase):
    def setUp(self):
        self.daily = SimpleNamespace(
            data=Data(date='2026-11-07'),
            pages_zip_path='/not-written/2026-11-07.zip',
            merged_pdf_path='/not-written/2026-11-07.pdf',
            pages_zip_name='2026-11-07.zip',
            merged_pdf_name='2026-11-07.pdf',
            image_paths=[
                Path('/not-written/images/01-frontpage.png'),
                Path('/not-written/images/02-highlights.png'),
            ],
            status=Status(downloaded=True),
            logger=MagicMock(),
        )
        self.config = Config.model_validate(
            {'oss': {'endpoint': 'https://oss.test'}}
        )

    def test_uploads_daily_files(self):
        with (
            patch('src.upload_to_oss.oss2.AuthV4'),
            patch('src.upload_to_oss.oss2.Bucket') as factory,
        ):
            upload_to_oss(self.config, self.daily)
            bucket = factory.return_value
            self.assertEqual(
                bucket.put_object_from_file.call_args_list,
                [
                    call(
                        '2026/11/07/2026-11-07.zip', self.daily.pages_zip_path
                    ),
                    call(
                        '2026/11/07/2026-11-07.pdf', self.daily.merged_pdf_path
                    ),
                ],
            )
            bucket.put_object.assert_not_called()
        self.assertTrue(self.daily.status.oss_uploaded)
        self.assertEqual(
            self.daily.status.oss_url,
            'https://oss.test/2026/11/07/2026-11-07.pdf',
        )

    def test_completed_upload_is_skipped(self):
        self.daily.status.oss_uploaded = True
        self.daily.status.oss_url = 'https://oss.test/saved.pdf'
        with (
            patch('src.upload_to_oss.oss2.AuthV4'),
            patch('src.upload_to_oss.oss2.Bucket') as factory,
        ):
            upload_to_oss(self.config, self.daily)
            factory.assert_not_called()
        self.assertEqual(
            self.daily.status.oss_url, 'https://oss.test/saved.pdf'
        )

    def test_images_upload_independently_of_daily_files(self):
        self.daily.status.oss_uploaded = True
        self.daily.status.oss_url = 'https://oss.test/saved.pdf'
        with (
            patch('src.upload_to_oss.oss2.AuthV4'),
            patch('src.upload_to_oss.oss2.Bucket') as factory,
        ):
            upload_images_to_oss(self.config, self.daily)
            self.assertEqual(
                factory.return_value.put_object_from_file.call_args_list,
                [
                    call(
                        '2026/11/07/images/01-frontpage.png',
                        '/not-written/images/01-frontpage.png'
                    ),
                    call(
                        '2026/11/07/images/02-highlights.png',
                        '/not-written/images/02-highlights.png'
                    ),
                ]
            )
            factory.reset_mock()
            upload_images_to_oss(self.config, self.daily)
            factory.assert_not_called()
        self.assertTrue(self.daily.status.oss_images_uploaded)
        self.assertEqual(
            self.daily.status.oss_url, 'https://oss.test/saved.pdf'
        )

    def test_failed_image_upload_can_be_retried(self):
        with (
            patch('src.upload_to_oss.oss2.AuthV4'),
            patch('src.upload_to_oss.oss2.Bucket') as factory,
        ):
            upload = factory.return_value.put_object_from_file
            upload.side_effect = [None, RuntimeError('upload failed')]
            with self.assertRaisesRegex(RuntimeError, 'upload failed'):
                upload_images_to_oss(self.config, self.daily)
            self.assertFalse(self.daily.status.oss_images_uploaded)
            self.assertFalse(self.daily.status.oss_uploaded)

            upload.side_effect = None
            upload_images_to_oss(self.config, self.daily)
        self.assertTrue(self.daily.status.oss_images_uploaded)
        self.assertFalse(self.daily.status.oss_uploaded)

    def test_missing_images_do_not_mark_upload_completed(self):
        self.daily.image_paths = []
        with self.assertRaisesRegex(ValueError, 'No generated images'):
            upload_images_to_oss(self.config, self.daily)
        self.assertFalse(self.daily.status.oss_images_uploaded)
