from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: str
    admin_ids: frozenset[int]
    log_level: str = "INFO"


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required. Set it in your local .env file.")
    try:
        admins = frozenset(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())
    except ValueError as exc:
        raise RuntimeError("ADMIN_IDS must contain comma-separated Telegram numeric IDs.") from exc
    path = os.getenv("DATABASE_PATH", "data/game.sqlite3").strip() or "data/game.sqlite3"
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return Settings(token, path, admins, os.getenv("LOG_LEVEL", "INFO").upper())
