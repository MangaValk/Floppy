from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TestCase

from app.providers import services


class InteractiveProviderBreakerTests(TestCase):
    """A dead provider must cost one timeout, not one per interactive call."""

    def setUp(self):
        cache.clear()

    def _call(self):
        return services.api_request("igdb", "GET", "https://example.test/x")

    def test_timeout_trips_breaker_for_interactive_calls_only(self):
        with patch.object(
            services,
            "resilient_request",
            side_effect=requests.exceptions.ReadTimeout("slow"),
        ) as send, services.interactive_request_scope():
            for _ in range(5):
                with self.assertRaises(services.ProviderAPIError):
                    self._call()
        self.assertEqual(send.call_count, 1)

        with patch.object(
            services,
            "resilient_request",
            side_effect=requests.exceptions.ReadTimeout("slow"),
        ) as send:
            with self.assertRaises(services.ProviderAPIError):
                self._call()
        self.assertEqual(send.call_count, 1)

    def test_gateway_error_trips_breaker_and_retries_once(self):
        response = requests.Response()
        response.status_code = 503
        with patch.object(services, "resilient_request", return_value=response) as send, \
                patch.object(services.time, "sleep"), \
                services.interactive_request_scope():
            with self.assertRaises(requests.exceptions.HTTPError):
                self._call()
            self.assertEqual(send.call_count, 2)
            with self.assertRaises(services.ProviderAPIError):
                self._call()
        self.assertEqual(send.call_count, 2)

    def test_plain_500_does_not_trip_breaker(self):
        response = requests.Response()
        response.status_code = 500
        with patch.object(services, "resilient_request", return_value=response), \
                patch.object(services.time, "sleep"), \
                services.interactive_request_scope():
            with self.assertRaises(requests.exceptions.HTTPError):
                self._call()
        self.assertIsNone(cache.get(services._provider_down_key("igdb")))
