"""Focused regression tests for security notification workflow helpers."""
import unittest
from unittest.mock import patch, MagicMock

from app.services.notification_provider_resilience import provider_for_channel
from app.core.security_events import classify_security_event
from app.services.security_notification_delivery import _post_json


class TestSecurityNotificationWorkflow(unittest.TestCase):
    def test_channel_maps_to_expected_provider(self):
        self.assertEqual(provider_for_channel("email"), "smtp")
        self.assertEqual(provider_for_channel("sms"), "twilio")
        self.assertEqual(provider_for_channel("webhook"), "webhook")

    def test_unknown_channel_is_preserved(self):
        self.assertEqual(provider_for_channel("push"), "push")

    def test_security_event_classification(self):
        self.assertEqual(classify_security_event("/auth/login", 401, {}),
                         ("login_failure", "low"))
        self.assertEqual(classify_security_event("/api/private", 403, {}),
                         ("authorization_denied", "low"))
        self.assertEqual(classify_security_event("/api/action", 429, {}),
                         ("rate_limit_block", "medium"))
        self.assertIsNone(classify_security_event("/api/ok", 200, {}))

    @patch("app.services.security_notification_delivery.urlopen")
    def test_webhook_sender_posts_json_and_returns_status(self, mocked_urlopen):
        response = MagicMock()
        response.status = 202
        mocked_urlopen.return_value.__enter__.return_value = response
        self.assertEqual(_post_json("https://example.invalid/hook",
                                    {"type": "test_alert"}), 202)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("application/json", request.get_header("Content-type"))
        self.assertEqual(request.data, b'{"type": "test_alert"}')


if __name__ == "__main__":
    unittest.main()
