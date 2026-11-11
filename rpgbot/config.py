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
        raise RuntimeError("BOT_TOKEN is required; set it in your private .env file.")

    try:
        admin_ids = frozenset(int(part.strip()) for part in os.getenv("ADMIN_IDS", "").split(",") if part.strip())
    except ValueError as exc:
        raise RuntimeError("ADMIN_IDS must be a comma-separated list of Telegram numeric IDs.") from exc

    path = os.getenv("DATABASE_PATH", "data/game.sqlite3").strip() or "data/game.sqlite3"
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    return Settings(token, path, admin_ids, os.getenv("LOG_LEVEL", "INFO").upper())
