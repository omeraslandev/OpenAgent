"""
Denetim İzi (Audit Trail) — zaman damgalı JSON log motoru.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.table import Table

from config import AUDIT_LOG_DIR


console = Console()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _local_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class AuditLogger:
    """Her ajan çalıştırması için tek bir JSON denetim dosyası üretir."""

    def __init__(
        self,
        *,
        readme_path: Optional[str] = None,
        model_name: Optional[str] = None,
        work_dir: Optional[str] = None,
        auto_approve: bool = False,
        server: Optional[str] = None,
        log_dir: Optional[Path] = None,
    ) -> None:
        self.log_dir = Path(log_dir) if log_dir else AUDIT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = _local_stamp()
        self.log_path = self.log_dir / f"audit_{self.session_id}.json"

        self._record: dict[str, Any] = {
            "session_id": self.session_id,
            "started_at": _utc_now_iso(),
            "finished_at": None,
            "readme_path": readme_path,
            "work_dir": work_dir,
            "model_name": model_name,
            "server": server,
            "auto_approve": auto_approve,
            "status": "running",
            "steps": [],
            "summary": None,
        }
        self._persist()

    # ------------------------------------------------------------------
    # Yazma
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        try:
            with self.log_path.open("w", encoding="utf-8") as fh:
                json.dump(self._record, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            console.print(f"[bold red]Denetim logu yazılamadı:[/] {exc}")

    def log_step(
        self,
        *,
        step_index: int,
        thought: str,
        action: str,
        command: str,
        status_message: str,
        user_approval: Optional[str],
        returncode: Optional[int],
        stdout: str,
        stderr: str,
        duration_seconds: float,
        error: Optional[str] = None,
    ) -> None:
        """Tek bir ajan adımını kaydeder."""
        entry: dict[str, Any] = {
            "step_index": step_index,
            "timestamp": _utc_now_iso(),
            "thought": thought,
            "action": action,
            "command": command,
            "status_message": status_message,
            "user_approval": user_approval,
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": round(duration_seconds, 3),
        }
        if error:
            entry["error"] = error
        self._record["steps"].append(entry)
        self._persist()

    def finalize(self, *, status: str, summary: Optional[str] = None) -> Path:
        """Oturumu kapatır ve log dosya yolunu döner."""
        self._record["finished_at"] = _utc_now_iso()
        self._record["status"] = status
        self._record["summary"] = summary
        self._persist()
        return self.log_path

    # ------------------------------------------------------------------
    # Listeleme
    # ------------------------------------------------------------------

    @staticmethod
    def list_audits(log_dir: Optional[Path] = None) -> list[Path]:
        directory = Path(log_dir) if log_dir else AUDIT_LOG_DIR
        if not directory.exists():
            return []
        return sorted(directory.glob("audit_*.json"), reverse=True)

    @classmethod
    def print_audit_table(cls, log_dir: Optional[Path] = None) -> None:
        files = cls.list_audits(log_dir)
        if not files:
            console.print("[yellow]Henüz denetim logu bulunamadı.[/]")
            return

        table = Table(title="Denetim Logları", show_lines=True)
        table.add_column("Dosya", style="cyan")
        table.add_column("Başlangıç", style="green")
        table.add_column("Durum")
        table.add_column("Model")
        table.add_column("Adım", justify="right")
        table.add_column("README", overflow="fold")

        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                table.add_row(path.name, "—", "corrupt", "—", "—", "—")
                continue

            status = str(data.get("status", "?"))
            status_style = {
                "completed": "[green]completed[/]",
                "failed": "[red]failed[/]",
                "aborted": "[yellow]aborted[/]",
                "running": "[blue]running[/]",
            }.get(status, status)

            table.add_row(
                path.name,
                str(data.get("started_at", "—")),
                status_style,
                str(data.get("model_name", "—")),
                str(len(data.get("steps", []))),
                str(data.get("readme_path") or "—"),
            )

        console.print(table)
