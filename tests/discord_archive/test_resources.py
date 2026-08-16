from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import httpx
from mika_archive.resources import (
    ResourceDownloader,
    UnsafeURLError,
    extract_media_targets,
    validate_public_url,
)


def public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


class ResourceTests(unittest.TestCase):
    def test_rejects_private_network_destinations(self) -> None:
        with self.assertRaises(UnsafeURLError):
            validate_public_url("http://internal.example/a", resolver=lambda _: ["127.0.0.1"])

    def test_download_hashes_and_deduplicates_content(self) -> None:
        payload = b"GIF89a useful"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=payload, headers={"content-type": "image/gif"}, request=request
            )

        with tempfile.TemporaryDirectory() as temp:
            downloader = ResourceDownloader(
                Path(temp),
                max_bytes=100,
                transport=httpx.MockTransport(handler),
                resolver=public_resolver,
            )
            first = downloader.download("https://example.com/a.gif")
            second = downloader.download("https://example.com/b.gif")
            digest = hashlib.sha256(payload).hexdigest()
            self.assertEqual(first.sha256, digest)
            self.assertEqual(first.path, second.path)
            self.assertEqual(first.path.read_bytes(), payload)
            self.assertEqual(len(list(Path(temp).rglob(digest))), 1)

    def test_size_cap_leaves_no_partial_blob(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"x" * 11, headers={"content-length": "11"}, request=request
            )

        with tempfile.TemporaryDirectory() as temp:
            downloader = ResourceDownloader(
                Path(temp),
                max_bytes=10,
                transport=httpx.MockTransport(handler),
                resolver=public_resolver,
            )
            result = downloader.download("https://example.com/large")
            self.assertEqual(result.status, "skipped")
            self.assertEqual(result.error, "resource exceeds 10 byte limit")
            self.assertEqual(list(Path(temp).rglob("*.part")), [])

    def test_permanent_http_error_is_terminal_skip_but_rate_limit_is_retryable(self) -> None:
        statuses = iter((404, 429))

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(next(statuses), request=request)

        with tempfile.TemporaryDirectory() as temp:
            downloader = ResourceDownloader(
                Path(temp),
                max_bytes=100,
                transport=httpx.MockTransport(handler),
                resolver=public_resolver,
            )
            self.assertEqual(downloader.download("https://example.com/missing").status, "skipped")
            self.assertEqual(downloader.download("https://example.com/limited").status, "failed")

    def test_extracts_known_open_graph_media_without_crawling_links(self) -> None:
        html = '<html><meta property="og:image" content="/preview.gif"><meta property="og:video" content="https://cdn.example/v.mp4"><a href="/not-crawled">x</a></html>'
        self.assertEqual(
            extract_media_targets(html, "https://example.com/page"),
            ["https://example.com/preview.gif", "https://cdn.example/v.mp4"],
        )


if __name__ == "__main__":
    unittest.main()
