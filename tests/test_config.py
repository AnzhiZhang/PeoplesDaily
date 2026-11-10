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

    def test_load_fills_missing_fields_and_save_preserves_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            path.write_text(
                'digest:\n  enabled: true\n'
                'x:\n  enabled: true\n  refresh_token: test-refresh\n'
            )
            config = Config.load(path)
            self.assertEqual(
                yaml.safe_load(path.read_text()), config.model_dump()
            )
            config.x.username = 'reader'
            config.save(path)
            restored = Config.load(path)
            self.assertEqual(restored.x.username, 'reader')
            self.assertEqual(restored.x.refresh_token, 'test-refresh')
            self.assertTrue(restored.digest.enabled)

    def test_telegram_and_x_require_digest(self):
        for channel, name in (('telegram', 'Telegram'), ('x', 'X')):
            with self.subTest(channel=channel):
                config = Config.model_validate({channel: {'enabled': True}})
                with self.assertRaisesRegex(
                    ValueError, name + ' requires digest.enabled'
                ):
                    config.validate()

    def test_digest_allows_both_channels(self):
        config = Config.model_validate(
            {
                'digest': {'enabled': True},
                'telegram': {'enabled': True},
                'x': {'enabled': True},
            }
        )
        config.validate()

    def test_logging_does_not_include_credentials(self):
        config = Config.model_validate(
            {
                'digest': {
                    'enabled': True,
                    'model': 'test-model',
                    'api_key': 'test-api-key',
                },
                'telegram': {'enabled': True, 'bot_token': 'test-bot-token'},
                'x': {
                    'enabled': True,
                    'client_secret': 'test-client-secret',
                    'refresh_token': 'test-refresh',
                },
            }
        )
        logger = MagicMock()
        config.log(logger)
        output = '\n'.join(call.args[0] for call in logger.info.call_args_list)
        self.assertIn('Digest enabled', output)
        self.assertIn('Digest model: test-model', output)
        self.assertIn('Telegram enabled', output)
        self.assertIn('X enabled', output)
        for secret in (
            'test-api-key',
            'test-bot-token',
            'test-client-secret',
            'test-refresh',
        ):
            self.assertNotIn(secret, output)

    def test_load_writes_missing_defaults_before_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            original = {
                'x': {'enabled': True, 'refresh_token': 'test-refresh'}
            }
            path.write_text(yaml.safe_dump(original))
            with self.assertRaisesRegex(
                ValueError, 'X requires digest.enabled'
            ):
                Config.load(path)
            saved = yaml.safe_load(path.read_text())
            self.assertEqual(
                saved, Config.model_validate(original).model_dump()
            )
            self.assertFalse(saved['digest']['enabled'])
            self.assertTrue(saved['x']['enabled'])
            self.assertEqual(saved['x']['refresh_token'], 'test-refresh')
