from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: str = "data/game.sqlite3"
    admin_ids: frozenset[int] = frozenset()
    log_level: str = "INFO"


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required; set it in a private .env file.")
    try:
        admins = frozenset(int(v.strip()) for v in os.getenv("ADMIN_IDS", "").split(",") if v.strip())
    except ValueError as exc:
        raise RuntimeError("ADMIN_IDS must be comma-separated Telegram numeric IDs.") from exc
    path = os.getenv("DATABASE_PATH", "data/game.sqlite3").strip() or "data/game.sqlite3"
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return Settings(token, path, admins, os.getenv("LOG_LEVEL", "INFO").upper())
