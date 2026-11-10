import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main
from src.config import Config
from src.status import Status


class DailyTaskTests(unittest.TestCase):
    def run_pipeline(
        self,
        *,
        digest=True,
        images=True,
        x=True,
        telegram=True,
        oss=True,
        failure=None,
        block_digest=False,
    ):
        events = []

        class Daily:
            def __init__(self, logger, date):
                self.data = SimpleNamespace(date='2026-11-07')
                self.status = Status()

            def get_today_peoples_daily(self):
                if failure == 'download':
                    raise RuntimeError('download failed')
                self.status.downloaded = True

            def save(self):
                events.append('save')
                if failure == 'save':
                    raise RuntimeError('save failed')

        started, release = threading.Event(), threading.Event()

        def action(name):
            def run(*args):
                if block_digest and name == 'digest':
                    started.set()
                    if not release.wait(3):
                        raise RuntimeError('Digest was not released by email')
                if block_digest and name == 'email':
                    if not started.wait(3):
                        raise RuntimeError('Digest did not start concurrently')
                    release.set()
                events.append(name)
                if failure == name:
                    raise RuntimeError(name + ' failed')

            return run

        config = Config.model_validate(
            {
                'digest': {'enabled': digest},
                'images': {'enabled': digest and images},
                'x': {'enabled': digest and x},
                'telegram': {'enabled': digest and telegram},
                'oss': {'enabled': oss},
                'email': {'enabled': oss},
            }
        )
        config.validate()
        with (
            ThreadPoolExecutor(max_workers=4) as pool,
            patch.multiple(
                main,
                executor=pool,
                logger=MagicMock(),
                TodayPeopleDaily=Daily,
                generate_digest=action('digest'),
                generate_images=action('images'),
                upload_to_oss=action('oss'),
                upload_images_to_oss=action('oss_images'),
                send_email=action('email'),
                send_telegram=action('telegram'),
                send_x=action('x'),
                func_timeout=lambda timeout, function: function(),
            ),
        ):
            if failure:
                with self.assertRaisesRegex(RuntimeError, failure + ' failed'):
                    main.daily_task(config)
            else:
                main.daily_task(config)
        return events

    def test_dependencies_and_parallel_digest(self):
        events = self.run_pipeline(block_digest=True)
        self.assertCountEqual(
            events,
            [
                'oss', 'oss_images', 'email', 'digest', 'images',
                'telegram', 'x', 'save'
            ],
        )
        self.assertEqual(events[-1], 'save')
        for before, after in (
            ('oss', 'email'),
            ('digest', 'images'),
            ('images', 'oss_images'),
            ('images', 'telegram'),
            ('images', 'x'),
        ):
            self.assertLess(events.index(before), events.index(after))

    def test_failures_are_propagated_after_saving_completed_work(self):
        for name in (
            'digest',
            'images',
            'oss',
            'oss_images',
            'email',
            'telegram',
            'x',
            'save',
        ):
            with self.subTest(task=name):
                events = self.run_pipeline(failure=name)
                self.assertEqual(events[-1], 'save')
                self.assertEqual(events.count('save'), 1)
                if name in ('digest', 'images'):
                    self.assertNotIn('x', events)
                    self.assertNotIn('telegram', events)
                    self.assertNotIn('oss_images', events)
                if name == 'oss':
                    self.assertNotIn('email', events)
                    self.assertIn('oss_images', events)
                if name == 'oss_images':
                    self.assertIn('email', events)
                    self.assertIn('telegram', events)
                    self.assertIn('x', events)

    def test_download_failure_does_not_save_incomplete_data(self):
        self.assertEqual(self.run_pipeline(failure='download'), [])

    def test_disabled_digest_channels(self):
        self.assertCountEqual(
            self.run_pipeline(digest=False), ['oss', 'email', 'save']
        )

    def test_telegram_only_generates_images_without_x(self):
        events = self.run_pipeline(x=False)
        self.assertIn('images', events)
        self.assertNotIn('x', events)
        self.assertLess(events.index('digest'), events.index('images'))
        self.assertLess(events.index('images'), events.index('telegram'))

    def test_images_generated_without_publishing_channels(self):
        events = self.run_pipeline(x=False, telegram=False)
        self.assertIn('digest', events)
        self.assertIn('images', events)
        self.assertNotIn('x', events)
        self.assertNotIn('telegram', events)

    def test_images_disabled_without_disabling_digest(self):
        events = self.run_pipeline(images=False, x=False, telegram=False)
        self.assertIn('digest', events)
        self.assertNotIn('images', events)
        self.assertNotIn('oss_images', events)

    def test_images_do_not_require_oss(self):
        events = self.run_pipeline(oss=False)
        self.assertIn('images', events)
        self.assertIn('telegram', events)
        self.assertIn('x', events)
        self.assertNotIn('oss', events)
        self.assertNotIn('oss_images', events)
