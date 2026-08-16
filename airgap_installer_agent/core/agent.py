"""
ReAct karar döngüsü — prompt yönetimi, LLM iletişimi ve self-healing.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from config import (
    DEFAULT_MODEL,
    LLM_TEMPERATURE,
    MAX_AGENT_STEPS,
    OLLAMA_HOST,
    SILENT_INSTALL_FLAGS,
    normalize_server_url,
)
from core.executor import ExecutionResult, PowerShellExecutor
from core.llm import (
    LLMServerUnavailable,
    is_connection_error,
    make_ollama_client,
)
from core.logger import AuditLogger
from core.security import SecurityGate
from tools.usb_manager import USBManager


console = Console()

ActionType = Literal["run_powershell", "manage_usb", "verify_step", "complete"]


class AgentAction(BaseModel):
    """LLM'den beklenen zorunlu JSON çıktı şeması."""

    thought: str = Field(..., min_length=1, description="Teknik gerekçe")
    action: ActionType
    command: str = Field(
        default="",
        description="PowerShell komutu veya USB parametresi (lock/unlock/status)",
    )
    status_message: str = Field(
        default="",
        description="Kullanıcıya gösterilecek durum mesajı",
    )

    @field_validator("command", mode="before")
    @classmethod
    def _none_to_empty(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, value: Any) -> str:
        if value is None:
            raise ValueError("action zorunludur")
        return str(value).strip().lower()


SYSTEM_PROMPT_TEMPLATE = """Sen hava boşluklu (air-gapped) kurumsal Windows 10/11 ortamlarında çalışan
güvenli bir kurulum otomasyon ajanısın. Türkçe düşün, teknik komutları Windows/PowerShell
sözdiziminde üret.

## Görevin
Verilen README / Runbook metnini adım adım oku; sessiz kurulumları yürüt; hata olursa
düzelt; tamamlanınca `complete` aksiyonunu çağır.

## Araçlar (action alanı)
1. `run_powershell` — `command` alanında tek bir PowerShell komutu çalıştır.
2. `manage_usb` — `command` alanında yalnızca: `lock` | `unlock` | `status`
3. `verify_step` — kurulum/doğrulama için PowerShell kontrol komutu çalıştır (run_powershell ile aynı motor).
4. `complete` — tüm adımlar bittiğinde; `command` boş olabilir, `status_message` özet olsun.

## Sessiz kurulum bayrakları
Mümkün olduğunca şu bayrakları kullan: __SILENT_FLAGS__
Örnekler:
- MSI: `msiexec /i setup.msi /qn /norestart`
- Inno Setup: `setup.exe /VERYSILENT /NORESTART /SP-`
- NSIS: `setup.exe /S`

## Kurallar
- Her yanıtın SADECE geçerli bir JSON nesnesi olsun. Markdown, açıklama veya kod çiti YOK.
- JSON şeması:
{{
  "thought": "Bu adımın teknik gerekçesi",
  "action": "run_powershell" | "manage_usb" | "verify_step" | "complete",
  "command": "powershell komutu veya usb parametresi",
  "status_message": "Kullanıcıya gösterilecek durum"
}}
- Yıkıcı komutlar YASAK (format, diskpart, bcdedit, sysprep, kök silme, kullanıcı silme).
- Çalışma dizini: {work_dir}
- README içeriğine sadık kal; uydurma indirme URL'si kullanma (ağ yok / air-gap).
- Önceki komut hata verdiyse stderr/returncode'u analiz et ve düzeltici komut öner.
- En fazla {max_steps} adımın var; gereksiz adım üretme.
"""


def _extract_json(text: str) -> dict[str, Any]:
    """LLM çıktısından JSON nesnesini ayıklar."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("LLM yanıtında JSON nesnesi bulunamadı.")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON kökü nesne (object) olmalıdır.")
    return data


class InstallerAgent:
    """README tabanlı ReAct kurulum ajanı."""

    def __init__(
        self,
        *,
        readme_path: Path,
        work_dir: Optional[Path] = None,
        model: str = DEFAULT_MODEL,
        auto_approve: bool = False,
        max_steps: int = MAX_AGENT_STEPS,
        ollama_host: str = OLLAMA_HOST,
    ) -> None:
        self.readme_path = Path(readme_path).expanduser().resolve()
        self.work_dir = (
            Path(work_dir).expanduser().resolve()
            if work_dir
            else self.readme_path.parent
        )
        self.model = model
        self.max_steps = max_steps
        self.auto_approve = auto_approve
        self.ollama_host = normalize_server_url(ollama_host)

        self.security = SecurityGate(auto_approve=auto_approve)
        self.executor = PowerShellExecutor(work_dir=str(self.work_dir))
        self.usb = USBManager(executor=PowerShellExecutor(require_admin=True))
        self.audit = AuditLogger(
            readme_path=str(self.readme_path),
            model_name=model,
            work_dir=str(self.work_dir),
            auto_approve=auto_approve,
            server=self.ollama_host,
        )

        self.client = make_ollama_client(self.ollama_host)
        self.messages: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _load_readme(self) -> str:
        if not self.readme_path.is_file():
            raise FileNotFoundError(f"README bulunamadı: {self.readme_path}")
        for encoding in ("utf-8", "utf-8-sig", "cp1254", "cp857", "latin-1"):
            try:
                return self.readme_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return self.readme_path.read_text(encoding="utf-8", errors="replace")

    def _build_system_prompt(self) -> str:
        template = SYSTEM_PROMPT_TEMPLATE.replace(
            "__SILENT_FLAGS__",
            ", ".join(SILENT_INSTALL_FLAGS),
        )
        return template.format(
            work_dir=str(self.work_dir),
            max_steps=self.max_steps,
        )

    def _seed_conversation(self, readme_text: str) -> None:
        self.messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {
                "role": "user",
                "content": (
                    "Aşağıdaki README/Runbook'u uygula. İlk JSON aksiyonunu üret.\n\n"
                    f"## Çalışma Dizini\n{self.work_dir}\n\n"
                    f"## README ({self.readme_path.name})\n"
                    f"```\n{readme_text}\n```"
                ),
            },
        ]

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def _ask_llm(self) -> AgentAction:
        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                with Status(
                    f"[bold cyan]LLM düşünüyor[/] ({self.model}, deneme {attempt}/3)...",
                    console=console,
                ):
                    response = self.client.chat(
                        model=self.model,
                        messages=self.messages,
                        options={"temperature": LLM_TEMPERATURE},
                        format="json",
                    )
                content = response["message"]["content"]
                self.messages.append({"role": "assistant", "content": content})
                payload = _extract_json(content)
                return AgentAction.model_validate(payload)
            except (ValidationError, ValueError, json.JSONDecodeError, KeyError) as exc:
                last_error = exc
                repair = (
                    "Önceki yanıt geçersizdi. SADECE şu şemada geçerli JSON döndür:\n"
                    '{"thought":"...","action":"run_powershell|manage_usb|verify_step|complete",'
                    '"command":"...","status_message":"..."}\n'
                    f"Hata: {exc}"
                )
                self.messages.append({"role": "user", "content": repair})
            except Exception as exc:
                if is_connection_error(exc):
                    raise LLMServerUnavailable(
                        self.ollama_host,
                        detail=str(exc),
                    ) from exc
                last_error = exc
                console.print(
                    Panel(
                        f"[red]LLM isteği başarısız:[/]\n{exc}",
                        title="Ollama Hatası",
                        border_style="red",
                    )
                )
                raise

        raise RuntimeError(f"LLM geçerli JSON üretemedi: {last_error}")

    # ------------------------------------------------------------------
    # Aksiyon yürütme
    # ------------------------------------------------------------------

    def _observation_from_result(self, result: ExecutionResult) -> str:
        parts = [
            f"returncode={result.returncode}",
            f"timed_out={result.timed_out}",
            f"stdout:\n{result.stdout[:4000]}",
            f"stderr:\n{result.stderr[:4000]}",
        ]
        if result.error:
            parts.append(f"error={result.error}")
        return "\n".join(parts)

    def _execute_action(self, action: AgentAction) -> tuple[
        Optional[str],
        Optional[int],
        str,
        str,
        float,
        Optional[str],
    ]:
        """
        Döner: (user_approval, returncode, stdout, stderr, duration, error)
        user_approval: approved | denied | skipped | blocked | None
        """
        started = time.perf_counter()

        if action.action == "complete":
            return "skipped", 0, "", "", time.perf_counter() - started, None

        if action.action == "manage_usb":
            usb_cmd = (action.command or "").strip().lower()
            if usb_cmd not in {"lock", "unlock", "status"}:
                msg = f"Geçersiz USB komutu: {action.command!r}"
                return "blocked", 1, "", msg, time.perf_counter() - started, msg

            # status için onay opsiyonel; lock/unlock için zorunlu (auto-approve hariç)
            if usb_cmd != "status":
                approved = self.security.request_approval(
                    command=f"USB {usb_cmd}",
                    thought=action.thought,
                    status_message=action.status_message,
                    action=action.action,
                )
                if not approved:
                    return "denied", None, "", "", time.perf_counter() - started, None

            ok = self.usb.manage(usb_cmd)
            duration = time.perf_counter() - started
            status = self.usb.get_usb_status() if usb_cmd == "status" else {}
            stdout = json.dumps(status, ensure_ascii=False) if status else (
                "OK" if ok else "FAILED"
            )
            return (
                "approved" if usb_cmd != "status" else "skipped",
                0 if ok else 1,
                stdout,
                "" if ok else "USB işlemi başarısız",
                duration,
                None if ok else "USB işlemi başarısız",
            )

        # run_powershell / verify_step
        command = action.command.strip()
        verdict = self.security.validate_command(command)
        if not verdict.allowed:
            console.print(
                Panel(
                    f"[red]{verdict.reason}[/]\n[dim]{command}[/]",
                    title="Kara Liste — Engellendi",
                    border_style="red",
                )
            )
            return (
                "blocked",
                1,
                "",
                verdict.reason,
                time.perf_counter() - started,
                verdict.reason,
            )

        approved = self.security.request_approval(
            command=command,
            thought=action.thought,
            status_message=action.status_message,
            action=action.action,
        )
        if not approved:
            return "denied", None, "", "", time.perf_counter() - started, None

        result = self.executor.run(command)
        return (
            "approved",
            result.returncode,
            result.stdout,
            result.stderr,
            result.duration_seconds,
            result.error,
        )

    # ------------------------------------------------------------------
    # Ana döngü
    # ------------------------------------------------------------------

    def run(self) -> int:
        """
        ReAct döngüsünü çalıştırır.
        Dönüş kodu: 0 başarı, 1 hata/iptal.
        """
        console.print(
            Panel(
                f"[bold]README:[/] {self.readme_path}\n"
                f"[bold]Çalışma dizini:[/] {self.work_dir}\n"
                f"[bold]LLM sunucu:[/] {self.ollama_host}\n"
                f"[bold]Model:[/] {self.model}\n"
                f"[bold]Otomatik onay:[/] {self.auto_approve}",
                title="OpenAgent",
                border_style="blue",
            )
        )

        try:
            readme_text = self._load_readme()
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/]")
            self.audit.finalize(status="failed", summary=str(exc))
            return 1

        self._seed_conversation(readme_text)

        for step in range(1, self.max_steps + 1):
            console.rule(f"[bold]Adım {step}/{self.max_steps}[/]")
            try:
                action = self._ask_llm()
            except LLMServerUnavailable as exc:
                self.audit.finalize(
                    status="failed",
                    summary=f"LLM sunucusuna ulaşılamadı: {exc.server}",
                )
                raise
            except Exception as exc:
                console.print(
                    Panel(
                        f"[red]Ajan durdu:[/]\n{exc}",
                        title="Hata",
                        border_style="red",
                    )
                )
                self.audit.finalize(status="failed", summary=str(exc))
                return 1

            console.print(
                Panel(
                    f"[bold]Düşünce:[/] {action.thought}\n"
                    f"[bold]Aksiyon:[/] {action.action}\n"
                    f"[bold]Mesaj:[/] {action.status_message}",
                    title="LLM Kararı",
                    border_style="cyan",
                )
            )

            if action.action == "complete":
                self.audit.log_step(
                    step_index=step,
                    thought=action.thought,
                    action=action.action,
                    command=action.command,
                    status_message=action.status_message,
                    user_approval="skipped",
                    returncode=0,
                    stdout="",
                    stderr="",
                    duration_seconds=0.0,
                )
                summary = action.status_message or "Kurulum tamamlandı."
                console.print(Panel(summary, title="Tamamlandı", border_style="green"))
                path = self.audit.finalize(status="completed", summary=summary)
                console.print(f"[dim]Denetim logu:[/] {path}")
                return 0

            (
                approval,
                returncode,
                stdout,
                stderr,
                duration,
                error,
            ) = self._execute_action(action)

            self.audit.log_step(
                step_index=step,
                thought=action.thought,
                action=action.action,
                command=action.command,
                status_message=action.status_message,
                user_approval=approval,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                error=error,
            )

            if approval == "denied":
                console.print("[yellow]Kullanıcı komutu reddetti. Oturum sonlandırılıyor.[/]")
                path = self.audit.finalize(
                    status="aborted",
                    summary="Kullanıcı onayı reddedildi.",
                )
                console.print(f"[dim]Denetim logu:[/] {path}")
                return 1

            # Self-healing: gözlemi konuşma geçmişine ekle
            observation = (
                f"Aksiyon sonucu (adım {step}):\n"
                f"action={action.action}\n"
                f"command={action.command}\n"
                f"user_approval={approval}\n"
                f"returncode={returncode}\n"
                f"stdout:\n{stdout[:4000]}\n"
                f"stderr:\n{stderr[:4000]}\n"
            )
            if error:
                observation += f"error={error}\n"

            failed = returncode not in (0, None) or bool(stderr.strip()) or bool(error)
            if failed and approval != "blocked":
                observation += (
                    "\nKomut başarısız veya uyarı üretti. Hatayı analiz et ve "
                    "düzeltici bir sonraki JSON aksiyonunu üret. "
                    "Düzeltilmesi imkânsızsa action=complete ile dürüst özet ver."
                )
            else:
                observation += (
                    "\nGözlemi dikkate alarak bir sonraki JSON aksiyonunu üret. "
                    "Tüm README adımları bittiyse action=complete kullan."
                )

            self.messages.append({"role": "user", "content": observation})

            if stdout.strip():
                console.print(Panel(stdout[-2000:], title="stdout", border_style="green"))
            if stderr.strip():
                console.print(Panel(stderr[-2000:], title="stderr", border_style="red"))

        console.print(
            f"[yellow]Maksimum adım sınırına ulaşıldı ({self.max_steps}).[/]"
        )
        path = self.audit.finalize(
            status="failed",
            summary=f"Maksimum adım ({self.max_steps}) aşıldı.",
        )
        console.print(f"[dim]Denetim logu:[/] {path}")
        return 1
