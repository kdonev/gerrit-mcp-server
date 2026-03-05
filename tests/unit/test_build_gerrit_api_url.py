import unittest
from unittest.mock import patch

from gerrit_mcp_server.main import _build_gerrit_api_url


class TestBuildGerritApiUrl(unittest.TestCase):

    def _http_basic_config(self):
        return {
            "gerrit_hosts": [
                {
                    "name": "Public",
                    "external_url": "https://public-gerrit.com/",
                    "authentication": {
                        "type": "http_basic",
                        "username": "user",
                        "password": "pass",
                    },
                }
            ]
        }

    def _gob_curl_config(self):
        return {
            "gerrit_hosts": [
                {
                    "name": "Fuchsia",
                    "external_url": "https://fuchsia-review.googlesource.com/",
                    "authentication": {"type": "gob_curl"},
                }
            ]
        }

    def test_adds_a_prefix_for_http_basic(self):
        """Write endpoints should use /a/ prefix with http_basic auth."""
        url = _build_gerrit_api_url(
            "https://public-gerrit.com",
            "changes/123/revisions/current/review",
            self._http_basic_config(),
        )
        self.assertEqual(
            url, "https://public-gerrit.com/a/changes/123/revisions/current/review"
        )

    def test_no_a_prefix_for_gob_curl(self):
        """Endpoints should NOT use /a/ prefix with gob_curl auth."""
        url = _build_gerrit_api_url(
            "https://fuchsia-review.googlesource.com",
            "changes/123/revisions/current/review",
            self._gob_curl_config(),
        )
        self.assertEqual(
            url,
            "https://fuchsia-review.googlesource.com/changes/123/revisions/current/review",
        )

    def test_strips_leading_slash_from_path(self):
        """Path with leading slash should not produce double slashes."""
        url = _build_gerrit_api_url(
            "https://public-gerrit.com",
            "/changes/123/abandon",
            self._http_basic_config(),
        )
        self.assertEqual(url, "https://public-gerrit.com/a/changes/123/abandon")

    def test_handles_query_params(self):
        """Query parameters in the path should be preserved."""
        url = _build_gerrit_api_url(
            "https://public-gerrit.com",
            "changes/?q=owner:me&n=10",
            self._http_basic_config(),
        )
        self.assertEqual(url, "https://public-gerrit.com/a/changes/?q=owner:me&n=10")


if __name__ == "__main__":
    unittest.main()
