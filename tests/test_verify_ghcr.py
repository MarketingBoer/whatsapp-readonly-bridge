import io
import json
import unittest

from scripts import verify_ghcr


class Response:
    def __init__(self, body, headers=None):
        self.body = json.dumps(body).encode()
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class VerifyGhcrTests(unittest.TestCase):
    def opener(self, request, timeout=10):
        if isinstance(request, str):
            return Response({"token": "anon-token"})
        tag = request.full_url.rsplit("/", 1)[-1]
        manifests = [
            {"platform": {"os": "linux", "architecture": "amd64"}},
            {"platform": {"os": "linux", "architecture": "arm64"}},
            {"platform": {"os": "unknown", "architecture": "unknown"}},
        ]
        return Response({"manifests": manifests},
                        {"Docker-Content-Digest": "sha256:" + "a" * 64})

    def test_verifies_matching_tags_and_platforms(self):
        findings = verify_ghcr.verify(
            "owner/repo", ["latest", "1.0.0"],
            {("linux", "amd64"), ("linux", "arm64")},
            opener=self.opener,
        )
        self.assertEqual(findings, [])

    def test_detects_divergent_tags_and_missing_platforms(self):
        calls = []

        def opener(request, timeout=10):
            if isinstance(request, str):
                return Response({"token": "token"})
            calls.append(request.full_url)
            digest = "sha256:" + ("b" if len(calls) == 2 else "a") * 64
            return Response({"manifests": [
                {"platform": {"os": "linux", "architecture": "amd64"}}
            ]}, {"Docker-Content-Digest": digest})

        findings = verify_ghcr.verify(
            "owner/repo", ["latest", "1.0.0"],
            {("linux", "amd64"), ("linux", "arm64")},
            opener=opener,
        )
        self.assertTrue(any("digest differs" in finding for finding in findings))
        self.assertTrue(any("missing platforms" in finding for finding in findings))


if __name__ == "__main__":
    unittest.main()
