"""
Merkezi yapılandırma — model, zaman aşımı, log yolları ve güvenlik eşikleri.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Proje kökü (PyInstaller onefile: .exe yanındaki klasör)
# ---------------------------------------------------------------------------
def get_app_root() -> Path:
    """Kaynak çalıştırmada paket dizini; frozen .exe'de çalıştırılabilirin klasörü."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


PROJECT_ROOT: Final[Path] = get_app_root()
AUDIT_LOG_DIR: Final[Path] = PROJECT_ROOT / "audit_logs"

# ---------------------------------------------------------------------------
# LLM / Merkezi Ollama sunucusu
# ---------------------------------------------------------------------------
DEFAULT_MODEL: Final[str] = "qwen2.5-coder:7b"
# Yerel veya uzak merkezi sunucu (ör. http://192.168.1.50:11434)
DEFAULT_OLLAMA_HOST: Final[str] = "http://localhost:11434"
OLLAMA_HOST: Final[str] = DEFAULT_OLLAMA_HOST
LLM_TEMPERATURE: Final[float] = 0.1
LLM_TIMEOUT_SECONDS: Final[int] = 120
LLM_CONNECT_TIMEOUT_SECONDS: Final[float] = 8.0

# ---------------------------------------------------------------------------
# Yürütme
# ---------------------------------------------------------------------------
COMMAND_TIMEOUT_SECONDS: Final[int] = 300
MAX_AGENT_STEPS: Final[int] = 20
POWERSHELL_EXE: Final[str] = "powershell.exe"

# Kodlama: Türkçe Windows konsol (OEM) → UTF-8 yedek
ENCODING_PRIMARY: Final[str] = "cp857"
ENCODING_FALLBACK: Final[str] = "utf-8"
ENCODING_ERRORS: Final[str] = "replace"

# ---------------------------------------------------------------------------
# Sessiz kurulum bayrakları (sistem promptunda kullanılır)
# ---------------------------------------------------------------------------
SILENT_INSTALL_FLAGS: Final[tuple[str, ...]] = (
    "/S",
    "/silent",
    "/quiet",
    "/qn",
    "/VERYSILENT",
    "/norestart",
    "/SP-",
)

# ---------------------------------------------------------------------------
# USB Registry yolları
# ---------------------------------------------------------------------------
USB_POLICY_HKLM: Final[str] = (
    r"HKLM\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices"
)
USB_POLICY_HKCU: Final[str] = (
    r"HKCU\Software\Policies\Microsoft\Windows\RemovableStorageDevices"
)
USBSTOR_SERVICE: Final[str] = r"HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR"

# USBSTOR Start: 3 = Manual/Enabled, 4 = Disabled
USBSTOR_START_ENABLED: Final[int] = 3
USBSTOR_START_DISABLED: Final[int] = 4


def normalize_server_url(url: str) -> str:
    """
    Sunucu adresini normalize eder.
    Örnekler: localhost:11434 → http://localhost:11434
              http://192.168.1.50:11434/ → http://192.168.1.50:11434
    """
    raw = (url or "").strip()
    if not raw:
        return DEFAULT_OLLAMA_HOST

    if "://" not in raw:
        raw = f"http://{raw}"

    parsed = urlparse(raw)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or parsed.path
    # path yanlışlıkla netloc'a kaymışsa düzelt
    if not parsed.netloc and parsed.path and "/" not in parsed.path.rstrip("/"):
        netloc = parsed.path

    netloc = netloc.rstrip("/")
    if not netloc:
        return DEFAULT_OLLAMA_HOST

    return f"{scheme}://{netloc}"
