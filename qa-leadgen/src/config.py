"""Configuration loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    load_dotenv()
    path = Path(config_path or "config.yaml")
    if not path.exists():
        path = Path("config.example.yaml")
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: dict[str, Any]) -> None:
    email = config.setdefault("email", {})
    env_map = {
        "SENDGRID_API_KEY": ("sendgrid_api_key", email),
        "MAILGUN_API_KEY": ("mailgun_api_key", email),
        "MAILGUN_DOMAIN": ("mailgun_domain", email),
        "SMTP_USER": ("smtp_user", email),
        "SMTP_PASSWORD": ("smtp_password", email),
    }
    for env_key, (cfg_key, section) in env_map.items():
        val = os.getenv(env_key)
        if val:
            section[cfg_key] = val

    sources = config.setdefault("sources", {})
    if os.getenv("INDEED_PUBLISHER_ID"):
        sources["indeed"] = True
    if os.getenv("UPWORK_ACCESS_TOKEN"):
        sources["upwork"] = True

    telegram = config.setdefault("telegram", {})
    env_telegram = {
        "TELEGRAM_BOT_TOKEN": "bot_token",
        "TELEGRAM_CHAT_ID": "chat_id",
    }
    for env_key, cfg_key in env_telegram.items():
        val = os.getenv(env_key)
        if val:
            telegram[cfg_key] = val


def ensure_output_dir(config: dict[str, Any]) -> Path:
    out_dir = Path(config.get("output", {}).get("directory", "./data"))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
