import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from src.config import Config
from src.data import Data
from src.status import Status
from src.upload_to_oss import upload_to_oss


class OSSUploadTests(unittest.TestCase):
    def setUp(self):
        self.daily = SimpleNamespace(
            data=Data(date='2026-11-07'),
            pages_zip_path='/not-written/2026-11-07.zip',
            merged_pdf_path='/not-written/2026-11-07.pdf',
            pages_zip_name='2026-11-07.zip',
            merged_pdf_name='2026-11-07.pdf',
            data_json_name='data.json',
            data_json_path='/not-written/data.json',
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
                    call(
                        '2026/11/07/data.json', self.daily.data_json_path
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
