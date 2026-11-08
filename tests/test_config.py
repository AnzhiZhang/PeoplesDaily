import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from src.config import Config


class ConfigTests(unittest.TestCase):
    def test_load_creates_default_file_and_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config/config.yaml'
            config = Config.load(path)
            self.assertEqual(
                yaml.safe_load(path.read_text()), config.model_dump()
            )

    def test_logging_does_not_include_credentials(self):
        config = Config.model_validate(
            {
                'digest': {
                    'enabled': True,
                    'model': 'test-model',
                    'api_key': 'test-api-key',
                },
                'telegram': {'enabled': True, 'bot_token': 'test-bot-token'},
            }
        )
        logger = MagicMock()
        config.log(logger)
        output = '\n'.join(call.args[0] for call in logger.info.call_args_list)
        self.assertIn('Digest enabled', output)
        self.assertIn('Digest model: test-model', output)
        self.assertIn('Telegram enabled', output)
        for secret in (
            'test-api-key',
            'test-bot-token',
        ):
            self.assertNotIn(secret, output)

    def test_load_validates_before_overwriting_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            content = 'telegram:\n  enabled: true\n'
            path.write_text(content)
            with self.assertRaisesRegex(
                ValueError, 'Telegram requires digest.enabled'
            ):
                Config.load(path)
            self.assertEqual(path.read_text(), content)
