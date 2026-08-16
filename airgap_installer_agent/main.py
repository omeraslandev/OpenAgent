#!/usr/bin/env python3
"""
Lokal / Merkezi LLM Destekli Güvenli CLI Otomasyon Ajanı — giriş noktası.

Kullanım:
  OpenAgent.exe run --readme <path> [--server http://192.168.1.50:11434] ...
  python main.py run --readme <path> [--dir <workdir>] [--server <url>] [--auto-approve] [--model <name>]
  python main.py usb --action [unlock|lock|status]
  python main.py audit --list
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Proje kökünü sys.path'e ekle (doğrudan python main.py / PyInstaller)
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import typer
from rich.console import Console
from rich.panel import Panel

from config import DEFAULT_MODEL, DEFAULT_OLLAMA_HOST, normalize_server_url
from core.llm import (
    LLMServerUnavailable,
    print_server_unreachable,
    probe_ollama_server,
)
from core.logger import AuditLogger
from core.security import is_admin


app = typer.Typer(
    name="OpenAgent",
    help="Hava boşluklu Windows ortamları için merkezi LLM destekli güvenli kurulum ajanı.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.command("run")
def run_cmd(
    readme: Path = typer.Option(
        ...,
        "--readme",
        "-r",
        help="Kurulum README / Runbook dosya yolu",
    ),
    work_dir: Optional[Path] = typer.Option(
        None,
        "--dir",
        "-d",
        help="Çalışma dizini (varsayılan: README'nin bulunduğu klasör)",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        help="Human-in-the-Loop onayını atla (dikkatli kullanın)",
    ),
    model: str = typer.Option(
        DEFAULT_MODEL,
        "--model",
        "-m",
        help="Ollama model adı",
    ),
    server: str = typer.Option(
        DEFAULT_OLLAMA_HOST,
        "--server",
        "-s",
        help="Merkezi Ollama sunucu adresi (ör. http://192.168.1.50:11434)",
    ),
) -> None:
    """README yönergelerini okuyup ReAct ajanıyla kurulum adımlarını yürütür."""
    from core.agent import InstallerAgent

    server_url = normalize_server_url(server)

    if sys.platform == "win32" and not is_admin():
        console.print(
            Panel(
                "[yellow]Yönetici yetkisi yok.[/] Bazı kurulum/USB adımları başarısız olabilir.\n"
                "Derlenmiş OpenAgent.exe UAC ile yükseltilmelidir (requireAdministrator).",
                title="Yetki Uyarısı",
                border_style="yellow",
            )
        )

    try:
        probe_ollama_server(server_url)
    except LLMServerUnavailable as exc:
        print_server_unreachable(exc.server, detail=exc.detail)
        raise typer.Exit(1) from None
    except Exception as exc:
        # Beklenmeyen ama bağlantı benzeri durumlar
        from core.llm import is_connection_error

        if is_connection_error(exc):
            print_server_unreachable(server_url, detail=str(exc))
            raise typer.Exit(1) from None
        console.print(
            Panel(
                f"[red]LLM sunucu kontrolü başarısız:[/]\n{exc}",
                title="Hata",
                border_style="red",
            )
        )
        raise typer.Exit(1) from None

    try:
        agent = InstallerAgent(
            readme_path=readme,
            work_dir=work_dir,
            model=model,
            auto_approve=auto_approve,
            ollama_host=server_url,
        )
        raise typer.Exit(agent.run())
    except LLMServerUnavailable as exc:
        print_server_unreachable(exc.server, detail=exc.detail)
        raise typer.Exit(1) from None


@app.command("usb")
def usb_cmd(
    action: str = typer.Option(
        ...,
        "--action",
        "-a",
        help="USB eylemi: unlock | lock | status",
    ),
) -> None:
    """USB portlarını kilitle / aç / durumunu sorgula."""
    from tools.usb_manager import USBManager

    normalized = action.strip().lower()
    if normalized not in {"unlock", "lock", "status"}:
        console.print("[red]--action unlock|lock|status olmalıdır.[/]")
        raise typer.Exit(2)

    manager = USBManager()
    ok = manager.manage(normalized)
    raise typer.Exit(0 if ok else 1)


@app.command("audit")
def audit_cmd(
    list_logs: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="Geçmiş denetim loglarını listele",
    ),
) -> None:
    """Denetim izi (audit) loglarını listeler."""
    if list_logs:
        AuditLogger.print_audit_table()
        raise typer.Exit(0)

    console.print("[yellow]Bir seçenek belirtin: --list[/]")
    raise typer.Exit(2)


def main() -> None:
    try:
        app()
    except LLMServerUnavailable as exc:
        print_server_unreachable(exc.server, detail=exc.detail)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
