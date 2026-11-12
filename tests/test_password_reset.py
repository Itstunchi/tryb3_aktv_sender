import gc
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import account_store as account_store_module
from account_store import AccountStore
from app import ADMIN_RECOVERY_EMAIL, app


class FakeSMTP:
    def __init__(self):
        self.messages = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def login(self, username, password):
        self.credentials_used = (username, password)

    def send_message(self, message):
        self.messages.append(message)
        return {}


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path_patch = patch.object(
            account_store_module,
            'DB_PATH',
            Path(self.temp_dir.name) / 'test.sqlite3',
        )
        self.db_path_patch.start()
        self.environment_patch = patch.dict(
            os.environ,
            {
                'BOOTSTRAP_ADMIN_EMAIL': 'admin@localhost',
                'BOOTSTRAP_ADMIN_PASSWORD': 'initial-admin-password-123',
            },
        )
        self.environment_patch.start()
        self.store = AccountStore()
        self.original_testing = app.config['TESTING']
        app.config['TESTING'] = True
        self.client = app.test_client()

    def tearDown(self):
        self.client = None
        app.config['TESTING'] = self.original_testing
        self.environment_patch.stop()
        self.db_path_patch.stop()
        gc.collect()
        self.temp_dir.cleanup()

    def csrf_token(self):
        response = self.client.get('/forgot-password')
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def test_reset_code_is_sent_only_to_recovery_mailbox_and_changes_admin_password(self):
        csrf = self.csrf_token()
        smtp = FakeSMTP()
        smtp_config = [{
            'enabled': True,
            'host': 'smtp.example.test',
            'port': 465,
            'username': ADMIN_RECOVERY_EMAIL,
            'password': 'test-only-password',
            'sender_email': ADMIN_RECOVERY_EMAIL,
            'use_ssl': True,
            'use_tls': False,
        }]

        with patch('app.account_store', self.store), \
                patch('app.config_manager.get_smtp_servers', return_value=smtp_config), \
                patch('app.smtplib.SMTP_SSL', return_value=smtp):
            requested = self.client.post(
                '/forgot-password',
                data={'csrf_token': csrf, 'email': 'admin@localhost'},
            )
            self.assertEqual(requested.status_code, 200)
            self.assertEqual(len(smtp.messages), 1)
            self.assertEqual(smtp.messages[0]['To'], ADMIN_RECOVERY_EMAIL)
            self.assertEqual(smtp.messages[0]['From'], ADMIN_RECOVERY_EMAIL)
            code_match = re.search(r'code is (\d{6})', smtp.messages[0].get_payload())
            self.assertIsNotNone(code_match)
            code = code_match.group(1)

            rejected = self.client.post(
                '/reset-password',
                data={
                    'csrf_token': csrf,
                    'email': 'admin@localhost',
                    'code': '000000' if code != '000000' else '000001',
                    'password': 'replacement-password-456',
                },
            )
            self.assertIn('invalid or expired', rejected.get_data(as_text=True))

            reset = self.client.post(
                '/reset-password',
                data={
                    'csrf_token': csrf,
                    'email': 'admin@localhost',
                    'code': code,
                    'password': 'replacement-password-456',
                },
            )

        self.assertIn('Password updated', reset.get_data(as_text=True))
        self.assertIsNone(self.store.login('admin@localhost', 'initial-admin-password-123'))
        self.assertTrue(self.store.login('admin@localhost', 'replacement-password-456'))

    def test_reset_code_is_limited_to_admin_and_expires(self):
        expiry = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.assertFalse(self.store.issue_admin_password_reset(
            'unknown@example.test', '123456', expiry,
        ))
        self.assertTrue(self.store.issue_admin_password_reset(
            'admin@localhost', '123456', expiry,
        ))
        self.assertFalse(self.store.reset_admin_password(
            'admin@localhost', '123456', 'replacement-password-456',
        ))
        self.assertIsNone(self.store.login('admin@localhost', 'replacement-password-456'))


if __name__ == '__main__':
    unittest.main()
