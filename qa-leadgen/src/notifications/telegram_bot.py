"""Interactive Telegram bot for start/stop scanning and on-demand reports."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import requests
import schedule
from rich.console import Console

from src.notifications.telegram import TelegramNotifier

console = Console()

HELP_TEXT = """QA Lead-Gen Bot Commands

/start — Start automatic job scanning (every {interval}h) + Excel delivery
/stop — Stop automatic scanning
/scan — Run a one-time job scan now
/report — Send current Excel tracker files
/scanreport — Scan jobs now, then send Excel files
/status — Show scanning status and last run times
/help — Show this message"""


class ScanningState:
    def __init__(self, state_file: Path, interval_hours: float = 12) -> None:
        self.state_file = state_file
        self.interval_hours = interval_hours
        self.data = self._load()

    def _load(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {
            "scanning_enabled": False,
            "last_scan_at": None,
            "last_report_at": None,
            "next_scan_at": None,
        }

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.data, indent=2))

    @property
    def scanning_enabled(self) -> bool:
        return bool(self.data.get("scanning_enabled"))

    def start_scanning(self) -> None:
        self.data["scanning_enabled"] = True
        self._schedule_next()
        self.save()

    def stop_scanning(self) -> None:
        self.data["scanning_enabled"] = False
        self.data["next_scan_at"] = None
        self.save()

    def record_scan(self) -> None:
        self.data["last_scan_at"] = datetime.utcnow().isoformat()
        if self.scanning_enabled:
            self._schedule_next()
        self.save()

    def record_report(self) -> None:
        self.data["last_report_at"] = datetime.utcnow().isoformat()
        self.save()

    def _schedule_next(self) -> None:
        nxt = datetime.utcnow() + timedelta(hours=self.interval_hours)
        self.data["next_scan_at"] = nxt.isoformat()

    def status_text(self) -> str:
        scanning = "ON" if self.scanning_enabled else "OFF"
        lines = [
            f"Scanning: {scanning}",
            f"Interval: every {self.interval_hours} hours",
            f"Last scan: {self._fmt(self.data.get('last_scan_at'))}",
            f"Last report: {self._fmt(self.data.get('last_report_at'))}",
            f"Next scheduled scan: {self._fmt(self.data.get('next_scan_at')) if self.scanning_enabled else 'n/a'}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt(value: str | None) -> str:
        if not value:
            return "never"
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            return str(value)


class TelegramBotController:
    def __init__(
        self,
        config: dict,
        data_dir: Path,
        fetch_fn: Callable[[], None],
        send_fn: Callable[[], bool],
    ) -> None:
        self.config = config
        self.data_dir = data_dir
        self.fetch_fn = fetch_fn
        self.send_fn = send_fn
        self.notifier = TelegramNotifier(config)
        tg_cfg = config.get("telegram", {})
        self.interval_hours = tg_cfg.get("interval_hours", 12)
        self.state = ScanningState(data_dir / "telegram_state.json", self.interval_hours)
        self._offset = 0
        self._scan_lock = False

    @property
    def is_ready(self) -> bool:
        return bool(self.notifier.bot_token and self.notifier.chat_id)

    def _api(self, method: str, **kwargs) -> dict:
        url = self.notifier._api_url(method)
        resp = requests.post(url, json=kwargs, timeout=35) if kwargs else requests.get(url, timeout=35)
        resp.raise_for_status()
        return resp.json()

    def reply(self, chat_id: str, text: str) -> None:
        self._api("sendMessage", chat_id=chat_id, text=text)

    def _authorized(self, chat_id: str | int) -> bool:
        return str(chat_id) == str(self.notifier.chat_id)

    def _run_scan(self, chat_id: str, send_report: bool = False) -> None:
        if self._scan_lock:
            self.reply(chat_id, "A scan is already in progress. Please wait.")
            return
        self._scan_lock = True
        try:
            self.reply(chat_id, "Starting job scan...")
            self.fetch_fn()
            self.state.record_scan()
            if send_report:
                self.reply(chat_id, "Scan complete. Sending Excel report...")
                self.send_fn()
                self.state.record_report()
                self.reply(chat_id, "Scan and report delivery finished.")
            else:
                self.reply(chat_id, "Job scan complete.")
        except Exception as exc:
            self.reply(chat_id, f"Scan failed: {exc}")
        finally:
            self._scan_lock = False

    def _run_report(self, chat_id: str) -> None:
        try:
            self.reply(chat_id, "Sending Excel report...")
            if self.send_fn():
                self.state.record_report()
                self.reply(chat_id, "Report sent.")
            else:
                self.reply(chat_id, "Failed to send report. Check logs.")
        except Exception as exc:
            self.reply(chat_id, f"Report failed: {exc}")

    def handle_command(self, chat_id: str, text: str) -> None:
        if not self._authorized(chat_id):
            console.print(f"[yellow]Ignored command from unauthorized chat {chat_id}[/yellow]")
            return

        cmd = text.strip().split()[0].lower().split("@")[0]

        if cmd in ("/start", "/startscan"):
            self.state.start_scanning()
            schedule.clear()
            schedule.every(self.interval_hours).hours.do(self._scheduled_scan)
            self.reply(
                chat_id,
                f"Automatic scanning started. Jobs will be scanned and Excel reports sent every "
                f"{self.interval_hours} hours.\n\n{self.state.status_text()}",
            )
            return

        if cmd in ("/stop", "/stopscan"):
            self.state.stop_scanning()
            schedule.clear()
            self.reply(chat_id, "Automatic scanning stopped.\n\n" + self.state.status_text())
            return

        if cmd == "/scan":
            self._run_scan(chat_id, send_report=False)
            return

        if cmd == "/report":
            self._run_report(chat_id)
            return

        if cmd in ("/scanreport", "/fetchreport"):
            self._run_scan(chat_id, send_report=True)
            return

        if cmd == "/status":
            jobs_file = self.data_dir / self.config["output"]["jobs_tracker"]
            summary = self.notifier.build_summary(jobs_file) if jobs_file.exists() else "No data yet."
            self.reply(chat_id, self.state.status_text() + "\n\n" + summary)
            return

        if cmd == "/help":
            self.reply(chat_id, HELP_TEXT.format(interval=self.interval_hours))
            return

        if cmd.startswith("/"):
            self.reply(chat_id, "Unknown command. Send /help for available commands.")

    def _scheduled_scan(self) -> None:
        if not self.state.scanning_enabled:
            return
        console.print("[cyan]Running scheduled Telegram scan...[/cyan]")
        try:
            self.fetch_fn()
            self.state.record_scan()
            self.send_fn()
            self.state.record_report()
            self.notifier.send_message(
                "Scheduled scan complete.\n" + self.state.status_text()
            )
        except Exception as exc:
            self.notifier.send_message(f"Scheduled scan failed: {exc}")

    def _poll_updates(self) -> list[dict]:
        url = (
            f"https://api.telegram.org/bot{self.notifier.bot_token}/getUpdates"
            f"?offset={self._offset}&timeout=25"
        )
        resp = requests.get(url, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return []
        return data.get("result", [])

    def run(self, *, auto_start_scanning: bool = False, run_on_boot: bool = False) -> None:
        if not self.is_ready:
            raise RuntimeError("Telegram bot_token and chat_id are required.")

        schedule.clear()

        if auto_start_scanning and not self.state.scanning_enabled:
            self.state.start_scanning()
            console.print("[green]Auto-started job scanning (automation config)[/green]")

        if self.state.scanning_enabled:
            schedule.every(self.interval_hours).hours.do(self._scheduled_scan)

        if run_on_boot:
            console.print("[cyan]Running initial fetch + report on boot...[/cyan]")
            try:
                self.fetch_fn()
                self.state.record_scan()
                self.send_fn()
                self.state.record_report()
            except Exception as exc:
                console.print(f"[red]Boot job failed: {exc}[/red]")
                self.notifier.send_message(f"Boot scan failed: {exc}")

        self.notifier.send_message(
            "QA Lead-Gen bot is online (automated).\n"
            f"Scanning: {'ON' if self.state.scanning_enabled else 'OFF'}\n\n"
            + HELP_TEXT.format(interval=self.interval_hours)
        )
        console.print("[green]Telegram bot listening for commands. Press Ctrl+C to stop.[/green]")
        console.print(f"Scanning state: {'ON' if self.state.scanning_enabled else 'OFF'}")

        while True:
            try:
                for update in self._poll_updates():
                    self._offset = update["update_id"] + 1
                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue
                    chat_id = str(message["chat"]["id"])
                    if not self._authorized(chat_id):
                        console.print(f"[yellow]Ignored message from unauthorized chat {chat_id}[/yellow]")
                        continue
                    text = message.get("text", "")
                    if text:
                        console.print(f"[dim]Command from Telegram: {text}[/dim]")
                        self.handle_command(chat_id, text)

                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                console.print("[yellow]Telegram bot stopped.[/yellow]")
                schedule.clear()
                break
            except Exception as exc:
                console.print(f"[red]Bot loop error: {exc}[/red]")
                time.sleep(5)
