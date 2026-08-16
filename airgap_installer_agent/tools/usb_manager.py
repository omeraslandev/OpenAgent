"""
USB Port açma / kapatma / durum sorgulama (Registry & GPO).
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from rich.console import Console
from rich.table import Table

from config import (
    USB_POLICY_HKCU,
    USB_POLICY_HKLM,
    USBSTOR_SERVICE,
    USBSTOR_START_DISABLED,
    USBSTOR_START_ENABLED,
)
from core.executor import PowerShellExecutor
from core.security import is_admin, require_admin


console = Console()


def _ps_escape(path: str) -> str:
    return path.replace("'", "''")


class USBManager:
    """
    RemovableStorageDevices GPO anahtarları ve USBSTOR servis Start değeri
    üzerinden USB depolamayı kontrol eder.
    """

    def __init__(self, executor: Optional[PowerShellExecutor] = None) -> None:
        self.executor = executor or PowerShellExecutor(require_admin=True)

    def _ensure_windows(self) -> bool:
        if sys.platform != "win32":
            console.print(
                "[red]USB yönetimi yalnızca Windows 10/11 üzerinde desteklenir.[/]"
            )
            return False
        return True

    def _run_ps(self, script: str) -> bool:
        result = self.executor.run(script)
        if not result.ok:
            console.print(f"[red]PowerShell hatası (kod={result.returncode}):[/]")
            if result.stderr:
                console.print(result.stderr.strip())
            if result.stdout:
                console.print(result.stdout.strip())
            return False
        return True

    def _gpupdate(self) -> bool:
        """Grup ilkesi güncellemesini sessizce zorlar."""
        result = self.executor.run_native(
            ["gpupdate.exe", "/force"],
            timeout=120,
        )
        if result.returncode != 0:
            console.print(
                f"[yellow]gpupdate uyarısı (kod={result.returncode}):[/] "
                f"{(result.stderr or result.stdout or '').strip()}"
            )
            return False
        return True

    def unlock_usb(self) -> bool:
        """
        USB depolamayı açar:
        - RemovableStorageDevices politika anahtarlarını siler
        - USBSTOR Start = 3
        - gpupdate /force
        """
        if not self._ensure_windows():
            return False
        if not require_admin():
            return False

        script = f"""
$ErrorActionPreference = 'Stop'
$paths = @(
    'Registry::{_ps_escape(USB_POLICY_HKLM)}',
    'Registry::{_ps_escape(USB_POLICY_HKCU)}'
)
foreach ($p in $paths) {{
    if (Test-Path $p) {{
        Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
    }}
}}
$usbStor = 'Registry::{_ps_escape(USBSTOR_SERVICE)}'
if (-not (Test-Path $usbStor)) {{
    New-Item -Path $usbStor -Force | Out-Null
}}
New-ItemProperty -Path $usbStor -Name 'Start' -PropertyType DWord -Value {USBSTOR_START_ENABLED} -Force | Out-Null
Write-Output 'USB_UNLOCK_OK'
"""
        console.print("[cyan]USB portları açılıyor...[/]")
        if not self._run_ps(script):
            return False
        self._gpupdate()
        console.print("[green]USB depolama açıldı (unlock).[/]")
        return True

    def lock_usb(self) -> bool:
        """
        USB depolamayı kilitler:
        - Deny_All = 1 (HKLM & HKCU RemovableStorageDevices)
        - USBSTOR Start = 4
        - gpupdate /force
        """
        if not self._ensure_windows():
            return False
        if not require_admin():
            return False

        script = f"""
$ErrorActionPreference = 'Stop'
$paths = @(
    'Registry::{_ps_escape(USB_POLICY_HKLM)}',
    'Registry::{_ps_escape(USB_POLICY_HKCU)}'
)
foreach ($p in $paths) {{
    if (-not (Test-Path $p)) {{
        New-Item -Path $p -Force | Out-Null
    }}
    New-ItemProperty -Path $p -Name 'Deny_All' -PropertyType DWord -Value 1 -Force | Out-Null
}}
$usbStor = 'Registry::{_ps_escape(USBSTOR_SERVICE)}'
if (-not (Test-Path $usbStor)) {{
    New-Item -Path $usbStor -Force | Out-Null
}}
New-ItemProperty -Path $usbStor -Name 'Start' -PropertyType DWord -Value {USBSTOR_START_DISABLED} -Force | Out-Null
Write-Output 'USB_LOCK_OK'
"""
        console.print("[cyan]USB portları kilitleniyor...[/]")
        if not self._run_ps(script):
            return False
        self._gpupdate()
        console.print("[green]USB depolama kilitlendi (lock).[/]")
        return True

    def get_usb_status(self) -> dict[str, Any]:
        """Mevcut USB kilit durumunu sözlük olarak döner."""
        status: dict[str, Any] = {
            "platform": sys.platform,
            "is_admin": is_admin(),
            "hklm_deny_all": None,
            "hkcu_deny_all": None,
            "usbstor_start": None,
            "policy_hklm_exists": False,
            "policy_hkcu_exists": False,
            "locked": None,
            "message": "",
        }

        if not self._ensure_windows():
            status["message"] = "Windows dışı platform"
            return status

        script = f"""
function Get-DenyAll($regPath) {{
    if (Test-Path $regPath) {{
        $item = Get-ItemProperty -Path $regPath -Name 'Deny_All' -ErrorAction SilentlyContinue
        if ($null -ne $item -and $null -ne $item.Deny_All) {{ return [string]$item.Deny_All }}
        return 'MISSING'
    }}
    return 'NO_KEY'
}}
$hklm = 'Registry::{_ps_escape(USB_POLICY_HKLM)}'
$hkcu = 'Registry::{_ps_escape(USB_POLICY_HKCU)}'
$usb  = 'Registry::{_ps_escape(USBSTOR_SERVICE)}'
$start = 'NO_KEY'
if (Test-Path $usb) {{
    $s = Get-ItemProperty -Path $usb -Name 'Start' -ErrorAction SilentlyContinue
    if ($null -ne $s -and $null -ne $s.Start) {{ $start = [string]$s.Start }} else {{ $start = 'MISSING' }}
}}
Write-Output ("HKLM_EXISTS=" + (Test-Path $hklm))
Write-Output ("HKCU_EXISTS=" + (Test-Path $hkcu))
Write-Output ("HKLM_DENY=" + (Get-DenyAll $hklm))
Write-Output ("HKCU_DENY=" + (Get-DenyAll $hkcu))
Write-Output ("USBSTOR_START=" + $start)
"""
        reader = PowerShellExecutor(require_admin=False)
        result = reader.run(script)
        if not result.ok:
            status["message"] = result.stderr or result.error or "Durum okunamadı"
            return status

        parsed: dict[str, str] = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if "=" in line:
                key, _, value = line.partition("=")
                parsed[key.strip()] = value.strip()

        status["policy_hklm_exists"] = parsed.get("HKLM_EXISTS", "").lower() == "true"
        status["policy_hkcu_exists"] = parsed.get("HKCU_EXISTS", "").lower() == "true"

        def _parse_deny(raw: Optional[str]) -> Optional[int]:
            if raw in (None, "NO_KEY", "MISSING", ""):
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        status["hklm_deny_all"] = _parse_deny(parsed.get("HKLM_DENY"))
        status["hkcu_deny_all"] = _parse_deny(parsed.get("HKCU_DENY"))

        start_raw = parsed.get("USBSTOR_START")
        try:
            status["usbstor_start"] = (
                int(start_raw) if start_raw not in (None, "NO_KEY", "MISSING") else None
            )
        except ValueError:
            status["usbstor_start"] = None

        deny_locked = status["hklm_deny_all"] == 1 or status["hkcu_deny_all"] == 1
        service_locked = status["usbstor_start"] == USBSTOR_START_DISABLED
        status["locked"] = bool(deny_locked or service_locked)

        if status["locked"]:
            status["message"] = "USB depolama kilitli görünüyor."
        else:
            status["message"] = "USB depolama açık görünüyor."

        return status

    def print_status(self) -> dict[str, Any]:
        status = self.get_usb_status()
        table = Table(title="USB Port Durumu", show_header=True)
        table.add_column("Alan", style="cyan")
        table.add_column("Değer")
        for key, value in status.items():
            table.add_row(key, str(value))
        console.print(table)
        return status

    def manage(self, action: str) -> bool:
        """Ajan / CLI için tek giriş noktası: lock | unlock | status."""
        normalized = (action or "").strip().lower()
        if normalized == "lock":
            return self.lock_usb()
        if normalized == "unlock":
            return self.unlock_usb()
        if normalized == "status":
            self.print_status()
            return True
        console.print(f"[red]Geçersiz USB eylemi:[/] {action!r} (lock|unlock|status)")
        return False


_default_manager: Optional[USBManager] = None


def _manager() -> USBManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = USBManager()
    return _default_manager


def unlock_usb() -> bool:
    return _manager().unlock_usb()


def lock_usb() -> bool:
    return _manager().lock_usb()


def get_usb_status() -> dict[str, Any]:
    return _manager().get_usb_status()
