"""Telegram setup helpers (chat ID discovery, webhook cleanup)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from rich.console import Console

console = Console()


def delete_webhook(bot_token: str) -> bool:
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{bot_token}/deleteWebhook",
            params={"drop_pending_updates": False},
            timeout=30,
        )
        return resp.json().get("ok", False)
    except Exception:
        return False


def get_bot_info(bot_token: str) -> dict | None:
    try:
        resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=30)
        data = resp.json()
        if data.get("ok"):
            return data["result"]
    except Exception:
        pass
    return None


def discover_chat_id(bot_token: str, timeout_seconds: int = 120) -> str | None:
    """Poll Telegram for the first message sent to the bot."""
    delete_webhook(bot_token)
    console.print(
        "[bold]Open Telegram and send any message to your bot[/bold] "
        "(e.g. /start or hello)."
    )
    console.print(f"Waiting up to {timeout_seconds} seconds...")

    offset = 0
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getUpdates",
                params={"offset": offset, "timeout": 10},
                timeout=20,
            )
            data = resp.json()
            if not data.get("ok"):
                console.print(f"[red]Telegram API error: {data}[/red]")
                return None

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if message:
                    chat = message["chat"]
                    chat_id = str(chat["id"])
                    name = chat.get("first_name") or chat.get("title") or "user"
                    console.print(f"[green]Found chat: {name} (ID: {chat_id})[/green]")
                    return chat_id
        except Exception as exc:
            console.print(f"[yellow]Polling error: {exc}[/yellow]")
        time.sleep(1)

    console.print("[red]No message received. Message your bot and run again.[/red]")
    return None


def save_chat_id_to_env(env_path: Path, chat_id: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("TELEGRAM_CHAT_ID="):
            new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def run_setup(config: dict, project_root: Path, timeout: int = 120) -> bool:
    tg = config.get("telegram", {})
    token = tg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        console.print("[red]TELEGRAM_BOT_TOKEN not set in .env or config.yaml[/red]")
        return False

    info = get_bot_info(token)
    if info:
        console.print(f"Bot: @{info.get('username')} ({info.get('first_name')})")
    else:
        console.print("[red]Invalid bot token.[/red]")
        return False

    chat_id = discover_chat_id(token, timeout_seconds=timeout)
    if not chat_id:
        return False

    env_path = project_root / ".env"
    save_chat_id_to_env(env_path, chat_id)
    console.print(f"[green]Saved TELEGRAM_CHAT_ID={chat_id} to {env_path}[/green]")
    return True
