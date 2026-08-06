"""Email sending with rate limiting and multiple provider support."""

from __future__ import annotations

import json
import os
import smtplib
import time
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from rich.console import Console

from src.models import EmailStatus, OutreachEmail

console = Console()


class RateLimiter:
    def __init__(self, daily_limit: int, state_file: Path) -> None:
        self.daily_limit = daily_limit
        self.state_file = state_file
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {"date": "", "count": 0}

    def _save_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self._state))

    def can_send(self) -> bool:
        today = date.today().isoformat()
        if self._state.get("date") != today:
            self._state = {"date": today, "count": 0}
            self._save_state()
        return self._state["count"] < self.daily_limit

    def record_send(self) -> None:
        today = date.today().isoformat()
        if self._state.get("date") != today:
            self._state = {"date": today, "count": 0}
        self._state["count"] += 1
        self._save_state()

    @property
    def remaining(self) -> int:
        today = date.today().isoformat()
        if self._state.get("date") != today:
            return self.daily_limit
        return max(0, self.daily_limit - self._state["count"])


class EmailSender:
    def __init__(self, config: dict, state_dir: Path) -> None:
        self.config = config
        self.email_config = config.get("email", {})
        self.user_config = config.get("user", {})
        daily_limit = self.email_config.get("daily_limit", 45)
        self.rate_limiter = RateLimiter(daily_limit, state_dir / "send_rate.json")

    def send(self, outreach: OutreachEmail, dry_run: bool = False) -> bool:
        if not self.rate_limiter.can_send():
            console.print(
                f"[red]Daily send limit reached ({self.email_config.get('daily_limit', 45)}/day). "
                "Try again tomorrow.[/red]"
            )
            return False

        if dry_run:
            console.print("[yellow]DRY RUN — email not sent[/yellow]")
            console.print(f"  To: {outreach.to_email}")
            console.print(f"  Subject: {outreach.subject}")
            return True

        provider = self.email_config.get("provider", "smtp")
        try:
            if provider == "sendgrid":
                self._send_sendgrid(outreach)
            elif provider == "mailgun":
                self._send_mailgun(outreach)
            else:
                self._send_smtp(outreach)
            self.rate_limiter.record_send()
            outreach.status = EmailStatus.SENT
            outreach.sent_at = datetime.utcnow()
            console.print(f"[green]Email sent to {outreach.to_email}[/green]")
            return True
        except Exception as exc:
            console.print(f"[red]Send failed: {exc}[/red]")
            return False

    def _send_smtp(self, outreach: OutreachEmail) -> None:
        msg = MIMEMultipart()
        msg["From"] = self.user_config.get("email", "")
        msg["To"] = outreach.to_email
        msg["Subject"] = outreach.subject
        msg.attach(MIMEText(outreach.body, "plain"))

        host = self.email_config.get("smtp_host", "smtp.gmail.com")
        port = self.email_config.get("smtp_port", 587)
        user = self.email_config.get("smtp_user", "") or self.user_config.get("email", "")
        password = self.email_config.get("smtp_password", "")

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)

    def _send_sendgrid(self, outreach: OutreachEmail) -> None:
        api_key = self.email_config.get("sendgrid_api_key") or os.getenv("SENDGRID_API_KEY", "")
        if not api_key:
            raise ValueError("SendGrid API key not configured")

        payload = {
            "personalizations": [{"to": [{"email": outreach.to_email}]}],
            "from": {"email": self.user_config.get("email", ""), "name": self.user_config.get("name", "")},
            "subject": outreach.subject,
            "content": [{"type": "text/plain", "value": outreach.body}],
        }
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()

    def _send_mailgun(self, outreach: OutreachEmail) -> None:
        api_key = self.email_config.get("mailgun_api_key") or os.getenv("MAILGUN_API_KEY", "")
        domain = self.email_config.get("mailgun_domain") or os.getenv("MAILGUN_DOMAIN", "")
        if not api_key or not domain:
            raise ValueError("Mailgun API key and domain not configured")

        resp = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data={
                "from": f"{self.user_config.get('name', '')} <{self.user_config.get('email', '')}>",
                "to": outreach.to_email,
                "subject": outreach.subject,
                "text": outreach.body,
            },
            timeout=30,
        )
        resp.raise_for_status()
