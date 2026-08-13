"""Persistent opt-out suppression list — companies/emails that must never be contacted again."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class SuppressionList:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return []

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self._entries, indent=2))

    def is_suppressed(self, email: str | None = None, company: str | None = None) -> bool:
        email_l = (email or "").strip().lower()
        company_l = (company or "").strip().lower()
        for entry in self._entries:
            if email_l and entry.get("email") == email_l:
                return True
            if company_l and entry.get("company") == company_l:
                return True
        return False

    def add(self, *, email: str = "", company: str = "", reason: str = "unsubscribe") -> None:
        email_l = email.strip().lower()
        company_l = company.strip().lower()
        if not email_l and not company_l:
            return
        if self.is_suppressed(email_l, company_l):
            return
        self._entries.append(
            {
                "email": email_l,
                "company": company_l,
                "reason": reason,
                "added_at": datetime.utcnow().isoformat(),
            }
        )
        self._save()

    def remove(self, *, email: str = "", company: str = "") -> bool:
        email_l = email.strip().lower()
        company_l = company.strip().lower()
        before = len(self._entries)
        self._entries = [
            e
            for e in self._entries
            if not ((email_l and e.get("email") == email_l) or (company_l and e.get("company") == company_l))
        ]
        if len(self._entries) != before:
            self._save()
            return True
        return False

    def all(self) -> list[dict]:
        return list(self._entries)
