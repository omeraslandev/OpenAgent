"""
Savunma sanayii güvenlik katmanı — kara liste, admin kontrolü, Human-in-the-Loop.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text


console = Console()


class TurkishConfirm(Confirm):
    """Evet/Hayır onayı — [E/H]."""

    choices = ["e", "h"]
    validate_error_message = "[prompt.invalid]Lütfen E (evet) veya H (hayır) girin"


# ---------------------------------------------------------------------------
# Yönetici kontrolü
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    """Windows'ta yönetici yetkisini doğrular; diğer OS'lerde False döner."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def require_admin(*, soft: bool = False) -> bool:
    """
    Yönetici değilse uyarı basar.
    soft=False ise False döner (çağıran karar verir); soft=True yalnızca uyarır.
    """
    if is_admin():
        return True
    msg = (
        "[bold red]UYARI:[/] Bu işlem yönetici (Administrator) yetkisi gerektirir. "
        "Programı 'Yönetici olarak çalıştır' ile yeniden başlatın."
    )
    console.print(msg)
    return soft


# ---------------------------------------------------------------------------
# Kara liste
# ---------------------------------------------------------------------------

# (regex, açıklama) — büyük/küçük harf duyarsız
_BLACKLIST_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"rmdir\s+/s\s+/q\s+[cC]:\\?\s*$", re.IGNORECASE),
        "Kök sürücü silme (rmdir /s /q C:\\)",
    ),
    (
        re.compile(r"rd\s+/s\s+/q\s+[cC]:\\?", re.IGNORECASE),
        "Kök sürücü silme (rd /s /q C:\\)",
    ),
    (
        re.compile(
            r"del\s+/[fqs]+\s+/[fqs]+\s+/[fqs]+\s+[cC]:\\Windows",
            re.IGNORECASE,
        ),
        "Windows dizinini silme",
    ),
    (
        re.compile(r"Remove-Item\s+.*-[rR]ecurse.*[cC]:\\(?:\s|$|\"|')", re.IGNORECASE),
        "Kök sürücü PowerShell silme",
    ),
    (
        re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
        "Disk formatlama",
    ),
    (
        re.compile(r"\bFormat-Volume\b", re.IGNORECASE),
        "Format-Volume cmdlet",
    ),
    (
        re.compile(r"\bsysprep\b", re.IGNORECASE),
        "Sysprep",
    ),
    (
        re.compile(r"\bbcdedit\b", re.IGNORECASE),
        "BCD düzenleme",
    ),
    (
        re.compile(r"\bdiskpart\b", re.IGNORECASE),
        "Diskpart",
    ),
    (
        re.compile(r"\bClear-Disk\b", re.IGNORECASE),
        "Clear-Disk",
    ),
    (
        re.compile(r"net\s+user\b.+/delete", re.IGNORECASE),
        "Kullanıcı silme (net user /delete)",
    ),
    (
        re.compile(r"Remove-LocalUser\b", re.IGNORECASE),
        "Remove-LocalUser",
    ),
    (
        re.compile(r"\bshutdown\b.+/[fr]", re.IGNORECASE),
        "Zorla kapatma/yeniden başlatma",
    ),
    (
        re.compile(r"Restart-Computer\b.*-Force", re.IGNORECASE),
        "Zorla yeniden başlatma",
    ),
    (
        re.compile(r"Stop-Computer\b", re.IGNORECASE),
        "Bilgisayarı kapatma",
    ),
    (
        re.compile(r"reg\s+delete\s+HKLM\\SYSTEM\\CurrentControlSet", re.IGNORECASE),
        "Kritik CurrentControlSet silme",
    ),
    (
        re.compile(r"cipher\s+/w:", re.IGNORECASE),
        "Disk üzerine yazma (cipher /w)",
    ),
    (
        re.compile(r"Takeown\s+/[fF]\s+[cC]:\\", re.IGNORECASE),
        "Kök sahiplik alma",
    ),
    (
        re.compile(r"icacls\s+[cC]:\\?\s+/[gG]rant", re.IGNORECASE),
        "Kök ACL değiştirme",
    ),
    (
        re.compile(r"Invoke-Expression\s*\(?\s*['\"]?\s*IEX", re.IGNORECASE),
        "Tehlikeli IEX / Invoke-Expression zinciri",
    ),
    (
        re.compile(
            r"(DownloadString|DownloadFile|FromBase64String).*(IEX|Invoke-Expression)",
            re.IGNORECASE | re.DOTALL,
        ),
        "Uzaktan kod indirme + yürütme",
    ),
]


@dataclass(frozen=True)
class SecurityVerdict:
    allowed: bool
    reason: str = ""
    matched_pattern: Optional[str] = None


class SecurityGate:
    """Komut doğrulama ve Human-in-the-Loop onay kapısı."""

    def __init__(self, *, auto_approve: bool = False) -> None:
        self.auto_approve = auto_approve

    def validate_command(self, command: str) -> SecurityVerdict:
        """Kara listeye karşı komutu tarar."""
        if not command or not command.strip():
            return SecurityVerdict(allowed=False, reason="Boş komut reddedildi.")

        normalized = command.strip()
        for pattern, description in _BLACKLIST_PATTERNS:
            if pattern.search(normalized):
                return SecurityVerdict(
                    allowed=False,
                    reason=f"Kara liste eşleşmesi: {description}",
                    matched_pattern=pattern.pattern,
                )
        return SecurityVerdict(allowed=True, reason="Kara liste kontrolü geçildi.")

    def request_approval(
        self,
        *,
        command: str,
        thought: str,
        status_message: str,
        action: str,
    ) -> bool:
        """
        Kullanıcıdan [E/H] onayı ister.
        --auto-approve verilmişse True döner.
        """
        if self.auto_approve:
            console.print(
                Panel(
                    Text.from_markup(
                        f"[bold yellow]OTOMATİK ONAY[/]\n"
                        f"[dim]{status_message}[/]\n\n"
                        f"[cyan]{command}[/]"
                    ),
                    title=f"Komut — {action}",
                    border_style="yellow",
                )
            )
            return True

        body = Text()
        body.append("Gerekçe: ", style="bold")
        body.append(f"{thought}\n\n")
        body.append("Durum: ", style="bold")
        body.append(f"{status_message}\n\n")
        body.append("Komut:\n", style="bold")
        body.append(command, style="cyan bold")

        console.print(
            Panel(
                body,
                title=f"[bold]Onay Gerekli — {action}[/]",
                border_style="magenta",
                expand=False,
            )
        )

        try:
            return TurkishConfirm.ask(
                "[bold]Bu komutu çalıştırmak istiyor musunuz?[/]",
                default=False,
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Onay iptal edildi.[/]")
            return False
