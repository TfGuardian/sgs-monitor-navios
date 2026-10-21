import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from vessel_monitor.integrations.vos import deliver_pending, integration_settings, sync_safely

ENV = {
    "VOS_INTEGRATION_URL": "https://example.supabase.co/functions/v1/receive-monitoring",
    "VOS_INTEGRATION_SECRET": "x" * 40,
}
ITEM = {"id": "delivery", "leaseToken": "lease",
        "payload": {"deliveryId": "stable-id"}}


@patch.dict(os.environ, ENV, clear=True)
class VOSIntegrationTests(unittest.TestCase):
    def client(self, *results):
        client = MagicMock()
        client.rpc.return_value.execute.side_effect = [
            SimpleNamespace(data=value) for value in results]
        return client

    def test_success_acknowledged_and_queue_drained(self):
        client = self.client(ITEM, True, None)
        post = MagicMock(return_value=SimpleNamespace(status_code=200))
        self.assertEqual(deliver_pending(client, post=post), 1)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertEqual(post.call_args.kwargs["json"], ITEM["payload"])
        self.assertEqual(client.rpc.call_args_list[1].args[1]["p_success"], True)

    def test_network_failure_is_persisted_without_secret(self):
        client = self.client(ITEM, True)
        post = MagicMock(side_effect=requests.ConnectionError("secret must not leak"))
        self.assertEqual(deliver_pending(client, post=post), 0)
        self.assertEqual(client.rpc.call_args.args[1]["p_error"], "TRANSPORT_ERROR")

    def test_http_error_stops_and_keeps_delivery_for_retry(self):
        for status in (301, 400, 401, 429, 503):
            with self.subTest(status=status):
                client = self.client(ITEM, True)
                post = MagicMock(return_value=SimpleNamespace(status_code=status))
                self.assertEqual(deliver_pending(client, post=post), 0)
                self.assertFalse(client.rpc.call_args.args[1]["p_success"])
                post.assert_called_once()

    def test_lost_ack_is_safe_to_retry_same_payload(self):
        post = MagicMock(return_value=SimpleNamespace(status_code=200))
        for _ in range(2):
            client = self.client(ITEM, False)
            self.assertEqual(deliver_pending(client, post=post), 0)
        self.assertEqual(post.call_args_list[0].kwargs["json"],
                         post.call_args_list[1].kwargs["json"])

    def test_limit_and_no_configuration(self):
        client = self.client(ITEM, True)
        post = MagicMock(return_value=SimpleNamespace(status_code=200))
        self.assertEqual(deliver_pending(client, limit=1, post=post), 1)
        with patch.dict(os.environ, {}, clear=True):
            client = MagicMock()
            self.assertIsNone(integration_settings())
            self.assertEqual(deliver_pending(client), 0)
            client.rpc.assert_not_called()

    def test_configuration_validation(self):
        for url in ("http://example.com/functions/v1/receive-monitoring",
                    "https://user:password@example.com/functions/v1/receive-monitoring",
                    "https://example.com/functions/v1/receive-monitoring?secret=x",
                    "https://example.com/functions/v1/receive-monitoring/other",
                    "https://example.com/other"):
            with patch.dict(os.environ, {"VOS_INTEGRATION_URL": url}):
                with self.assertRaises(ValueError):
                    integration_settings()

    def test_sync_failure_does_not_stop_observer(self):
        with patch("vessel_monitor.integrations.vos.deliver_pending", side_effect=RuntimeError), \
             patch("builtins.print") as output:
            sync_safely(object())
            self.assertIn("deferred", output.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
