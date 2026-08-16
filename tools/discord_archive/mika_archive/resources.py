from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


class UnsafeURLError(ValueError):
    pass


Resolver = Callable[[str], Iterable[str]]


def _system_resolver(host: str) -> list[str]:
    return sorted({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})


def validate_public_url(url: str, *, resolver: Resolver = _system_resolver) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise UnsafeURLError("only unauthenticated HTTP(S) URLs are allowed")
    try:
        addresses = list(resolver(parts.hostname))
    except OSError as error:
        raise UnsafeURLError("host resolution failed") from error
    if not addresses:
        raise UnsafeURLError("host did not resolve")
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise UnsafeURLError("destination is not a public network address")
    host = parts.hostname.lower()
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, ""))


@dataclass(frozen=True, slots=True)
class DownloadResult:
    status: str
    final_url: str
    http_status: int | None = None
    mime_type: str | None = None
    byte_count: int | None = None
    sha256: str | None = None
    path: Path | None = None
    error: str | None = None


class ResourceDownloader:
    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int,
        transport: httpx.BaseTransport | None = None,
        resolver: Resolver = _system_resolver,
    ) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.resolver = resolver
        self.root.mkdir(parents=True, exist_ok=True)
        self._temp = self.root.parent / ".partial"
        self._temp.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(60, connect=20),
            follow_redirects=False,
            headers={"User-Agent": "MikaLocalArchive/1.0 (+local preservation)"},
        )

    def close(self) -> None:
        self.client.close()

    def download(self, url: str) -> DownloadResult:
        current = url
        try:
            for _ in range(8):
                current = validate_public_url(current, resolver=self.resolver)
                with self.client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            return DownloadResult(
                                "failed",
                                current,
                                response.status_code,
                                error="redirect missing location",
                            )
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        retryable = response.status_code == 429 or response.status_code >= 500
                        return DownloadResult(
                            "failed" if retryable else "skipped",
                            current,
                            response.status_code,
                            error=f"HTTP {response.status_code}",
                        )
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > self.max_bytes:
                        return DownloadResult(
                            "skipped",
                            current,
                            response.status_code,
                            error=f"resource exceeds {self.max_bytes} byte limit",
                        )
                    return self._store_stream(current, response)
            return DownloadResult("failed", current, error="too many redirects")
        except UnsafeURLError as error:
            return DownloadResult("skipped", current, error=str(error))
        except (httpx.HTTPError, OSError, ValueError) as error:
            return DownloadResult("failed", current, error=f"{type(error).__name__}: {error}")

    def _store_stream(self, final_url: str, response: httpx.Response) -> DownloadResult:
        digest = hashlib.sha256()
        count = 0
        descriptor, temp_name = tempfile.mkstemp(prefix="resource-", suffix=".part", dir=self._temp)
        try:
            with os.fdopen(descriptor, "wb") as output:
                for chunk in response.iter_bytes(1024 * 1024):
                    count += len(chunk)
                    if count > self.max_bytes:
                        return DownloadResult(
                            "skipped",
                            final_url,
                            response.status_code,
                            error=f"resource exceeds {self.max_bytes} byte limit",
                        )
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            hexdigest = digest.hexdigest()
            destination = self.root / hexdigest[:2] / hexdigest
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                Path(temp_name).unlink(missing_ok=True)
            else:
                Path(temp_name).replace(destination)
            return DownloadResult(
                "stored",
                final_url,
                response.status_code,
                response.headers.get("content-type", "application/octet-stream")
                .split(";", 1)[0]
                .strip()
                .lower(),
                count,
                hexdigest,
                destination.resolve(),
                None,
            )
        finally:
            Path(temp_name).unlink(missing_ok=True)


class _OpenGraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value for key, value in attrs if value is not None}
        prop = values.get("property") or values.get("name")
        if (
            prop
            and prop.lower()
            in {
                "og:image",
                "og:image:url",
                "og:video",
                "og:video:url",
                "twitter:image",
                "twitter:player:stream",
            }
            and values.get("content")
        ):
            self.targets.append(values["content"])


def extract_media_targets(html: str, base_url: str) -> list[str]:
    parser = _OpenGraphParser()
    parser.feed(html)
    result: list[str] = []
    for value in parser.targets:
        target = urljoin(base_url, value)
        if target not in result:
            result.append(target)
    return result
