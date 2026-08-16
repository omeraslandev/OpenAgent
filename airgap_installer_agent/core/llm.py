"""
Merkezi LLM (Ollama) sunucu erişimi ve bağlantı hatalarının temiz gösterimi.
"""

from __future__ import annotations

from typing import Optional

import httpx
import ollama
from rich.console import Console
from rich.panel import Panel

from config import (
    DEFAULT_OLLAMA_HOST,
    LLM_CONNECT_TIMEOUT_SECONDS,
    LLM_TIMEOUT_SECONDS,
    normalize_server_url,
)


console = Console()

SERVER_UNREACHABLE_MESSAGE = (
    "Merkezi LLM sunucusuna ulaşılamadı. IP adresini ve portu kontrol edin."
)


class LLMServerUnavailable(Exception):
    """Ollama sunucusuna erişilemediğinde yükseltillir (traceback yerine Rich paneli)."""

    def __init__(
        self,
        server: str,
        *,
        detail: Optional[str] = None,
    ) -> None:
        self.server = server
        self.detail = detail
        super().__init__(SERVER_UNREACHABLE_MESSAGE)


def make_ollama_client(host: str) -> ollama.Client:
    """Yerel veya uzak Ollama sunucusu için istemci oluşturur."""
    normalized = normalize_server_url(host)
    timeout = httpx.Timeout(
        LLM_TIMEOUT_SECONDS,
        connect=LLM_CONNECT_TIMEOUT_SECONDS,
    )
    try:
        return ollama.Client(host=normalized, timeout=timeout)
    except TypeError:
        try:
            return ollama.Client(host=normalized, timeout=LLM_TIMEOUT_SECONDS)
        except TypeError:
            return ollama.Client(host=normalized)


def is_connection_error(exc: BaseException) -> bool:
    """Ağ / sunucu erişim hatalarını ayırt eder."""
    if isinstance(
        exc,
        (
            LLMServerUnavailable,
            ConnectionError,
            TimeoutError,
            OSError,
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.ProxyError,
        ),
    ):
        return True

    # ollama / httpx sarmalayıcıları
    name = type(exc).__name__.lower()
    if any(
        token in name
        for token in ("connect", "timeout", "network", "remote", "httpstatus")
    ):
        # ResponseError (ör. 404 model yok) bağlantı hatası değildir
        if "response" in name and "connect" not in name:
            return False
        if "connect" in name or "timeout" in name or "network" in name:
            return True

    message = str(exc).lower()
    needles = (
        "connect",
        "connection refused",
        "failed to establish",
        "timed out",
        "timeout",
        "name or service not known",
        "nodename nor servname",
        "getaddrinfo",
        "actively refused",
        "unreachable",
        "no route to host",
        "10061",  # WSAECONNREFUSED
        "10060",  # WSAETIMEDOUT
    )
    return any(n in message for n in needles)


def probe_ollama_server(host: str = DEFAULT_OLLAMA_HOST) -> str:
    """
    Sunucuya hafif bir sağlık kontrolü yapar.
    Başarılıysa normalize edilmiş URL döner; aksi halde LLMServerUnavailable yükseltir.
    """
    server = normalize_server_url(host)
    client = make_ollama_client(server)
    try:
        # list() / tags — model listesi; bağlantı doğrulaması için yeterli
        client.list()
    except Exception as exc:
        if is_connection_error(exc):
            raise LLMServerUnavailable(server, detail=str(exc)) from exc
        # Örneğin API sürüm uyumsuzluğu — yine de sunucuya ulaşıldı sayılabilir;
        # asıl chat sırasında netleşir. Bağlantı dışı hataları yukarı ilet.
        raise
    return server


def print_server_unreachable(server: str, *, detail: Optional[str] = None) -> None:
    """Traceback yerine Rich paneliyle kullanıcı dostu hata basar."""
    body = (
        f"[bold red]{SERVER_UNREACHABLE_MESSAGE}[/]\n\n"
        f"[bold]Sunucu:[/] {server}\n"
        "[dim]Örnek: --server http://192.168.1.50:11434[/]"
    )
    if detail:
        body += f"\n\n[dim]Ayrıntı: {detail}[/]"
    console.print(
        Panel(
            body,
            title="Bağlantı Hatası",
            border_style="red",
        )
    )
