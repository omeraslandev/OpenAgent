"""
PowerShell yürütme motoru — admin farkındalığı, timeout, Türkçe encoding.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional, Sequence

from rich.console import Console

from config import (
    COMMAND_TIMEOUT_SECONDS,
    ENCODING_ERRORS,
    ENCODING_FALLBACK,
    ENCODING_PRIMARY,
    POWERSHELL_EXE,
)
from core.security import is_admin


console = Console()


@dataclass
class ExecutionResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None


def decode_output(raw: bytes) -> str:
    """cp857 → utf-8 → latin-1 yedek zinciri ile baytları metne çevirir."""
    if not raw:
        return ""
    for encoding in (ENCODING_PRIMARY, ENCODING_FALLBACK, "cp1254", "latin-1"):
        try:
            return raw.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    return raw.decode(ENCODING_FALLBACK, errors=ENCODING_ERRORS)


class PowerShellExecutor:
    """powershell -NoProfile -ExecutionPolicy Bypass ile komut çalıştırır."""

    def __init__(
        self,
        *,
        timeout: int = COMMAND_TIMEOUT_SECONDS,
        work_dir: Optional[str] = None,
        require_admin: bool = False,
    ) -> None:
        self.timeout = timeout
        self.work_dir = work_dir
        self.require_admin = require_admin

    def _check_admin(self) -> Optional[str]:
        if self.require_admin and sys.platform == "win32" and not is_admin():
            return "Yönetici yetkisi gerekli; komut çalıştırılmadı."
        return None

    def run(self, command: str, *, timeout: Optional[int] = None) -> ExecutionResult:
        """Tek bir PowerShell komutunu yürütür."""
        admin_err = self._check_admin()
        if admin_err:
            return ExecutionResult(
                command=command,
                returncode=1,
                stdout="",
                stderr=admin_err,
                duration_seconds=0.0,
                error=admin_err,
            )

        effective_timeout = timeout if timeout is not None else self.timeout
        argv: Sequence[str] = [
            POWERSHELL_EXE,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]

        started = time.perf_counter()
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                timeout=effective_timeout,
                cwd=self.work_dir,
                check=False,
            )
            duration = time.perf_counter() - started
            return ExecutionResult(
                command=command,
                returncode=int(completed.returncode),
                stdout=decode_output(completed.stdout),
                stderr=decode_output(completed.stderr),
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - started
            stdout = decode_output(exc.stdout or b"")
            stderr = decode_output(exc.stderr or b"")
            msg = f"Komut zaman aşımına uğradı ({effective_timeout}s)."
            return ExecutionResult(
                command=command,
                returncode=124,
                stdout=stdout,
                stderr=stderr or msg,
                duration_seconds=duration,
                timed_out=True,
                error=msg,
            )
        except FileNotFoundError:
            duration = time.perf_counter() - started
            msg = f"PowerShell bulunamadı: {POWERSHELL_EXE}"
            return ExecutionResult(
                command=command,
                returncode=127,
                stdout="",
                stderr=msg,
                duration_seconds=duration,
                error=msg,
            )
        except OSError as exc:
            duration = time.perf_counter() - started
            msg = f"Yürütme hatası: {exc}"
            return ExecutionResult(
                command=command,
                returncode=1,
                stdout="",
                stderr=msg,
                duration_seconds=duration,
                error=msg,
            )

    def run_native(
        self,
        argv: Sequence[str],
        *,
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """PowerShell dışı native komut (ör. gpupdate) çalıştırır."""
        admin_err = self._check_admin()
        if admin_err:
            return ExecutionResult(
                command=" ".join(argv),
                returncode=1,
                stdout="",
                stderr=admin_err,
                duration_seconds=0.0,
                error=admin_err,
            )

        effective_timeout = timeout if timeout is not None else self.timeout
        cmd_str = " ".join(argv)
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                timeout=effective_timeout,
                cwd=self.work_dir,
                check=False,
            )
            duration = time.perf_counter() - started
            return ExecutionResult(
                command=cmd_str,
                returncode=int(completed.returncode),
                stdout=decode_output(completed.stdout),
                stderr=decode_output(completed.stderr),
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - started
            return ExecutionResult(
                command=cmd_str,
                returncode=124,
                stdout=decode_output(exc.stdout or b""),
                stderr=decode_output(exc.stderr or b"")
                or f"Zaman aşımı ({effective_timeout}s)",
                duration_seconds=duration,
                timed_out=True,
                error=f"Zaman aşımı ({effective_timeout}s)",
            )
        except OSError as exc:
            duration = time.perf_counter() - started
            return ExecutionResult(
                command=cmd_str,
                returncode=1,
                stdout="",
                stderr=str(exc),
                duration_seconds=duration,
                error=str(exc),
            )
