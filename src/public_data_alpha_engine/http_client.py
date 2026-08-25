from __future__ import annotations

import time
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class HttpResponse:
    body: bytes
    status: int
    content_type: str
    elapsed_ms: int
    retries: int


class HttpClient:
    def __init__(self, timeout: float = 20.0, max_retries: int = 2) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        system_ca = Path("/etc/ssl/cert.pem")
        self.ssl_context = ssl.create_default_context(cafile=str(system_ca) if system_ca.exists() else None)

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
    ) -> HttpResponse:
        last_error: Exception | None = None
        started = time.monotonic()
        for attempt in range(self.max_retries + 1):
            try:
                request = urllib.request.Request(
                    url,
                    data=data,
                    method=method,
                    headers={"User-Agent": "OpportunityFoundry-PDAE/0.1", **dict(headers or {})},
                )
                with urllib.request.urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                    body = response.read()
                    elapsed = int((time.monotonic() - started) * 1000)
                    return HttpResponse(
                        body=body,
                        status=response.status,
                        content_type=response.headers.get_content_type(),
                        elapsed_ms=elapsed,
                        retries=attempt,
                    )
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
        assert last_error is not None
        raise last_error
