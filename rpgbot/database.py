from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4


class Database:
    """SQLite persistence with foreign keys, WAL, and explicit transactions."""

    def __init__(self, path: str | Path):
        raw = str(path)
        self.memory = raw == ":memory:"
        self.uri = self.memory or raw.startswith("file:")
        self.path = f"file:rpg-{uuid4().hex}?mode=memory&cache=shared" if self.memory else raw
        self.anchor = sqlite3.connect(self.path, uri=True) if self.memory else None
        if not self.memory and not self.uri:
            Path(raw).expanduser().parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=20, isolation_level=None, uri=self.uri)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=20000")
        if not self.memory:
            con.execute("PRAGMA journal_mode=WAL")
        return con

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @contextmanager
    def reader(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            yield con
        finally:
            con.close()

    def initialize(self) -> None:
        with self.transaction() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS players(
              telegram_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT NOT NULL,
              level INTEGER NOT NULL DEFAULT 1 CHECK(level>=1), xp INTEGER NOT NULL DEFAULT 0 CHECK(xp>=0),
              coins INTEGER NOT NULL DEFAULT 100 CHECK(coins>=0), gems INTEGER NOT NULL DEFAULT 0 CHECK(gems>=0),
              energy INTEGER NOT NULL DEFAULT 100 CHECK(energy>=0), max_energy INTEGER NOT NULL DEFAULT 100 CHECK(max_energy>=1),
              active_character TEXT NOT NULL DEFAULT 'goku', last_daily TEXT, daily_streak INTEGER NOT NULL DEFAULT 0,
              last_raid_at INTEGER NOT NULL DEFAULT 0, banned INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS fighters(
              player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
              fighter_id TEXT NOT NULL, shards INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(player_id,fighter_id));
            CREATE TABLE IF NOT EXISTS inventory(
              player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
              item_id TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),
              PRIMARY KEY(player_id,item_id));
            CREATE TABLE IF NOT EXISTS quests(
              player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
              day TEXT NOT NULL, quest_id TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
              claimed INTEGER NOT NULL DEFAULT 0 CHECK(claimed IN (0,1)), PRIMARY KEY(player_id,day,quest_id));
            CREATE TABLE IF NOT EXISTS clans(
              id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
              leader_id INTEGER NOT NULL REFERENCES players(telegram_id), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS clan_members(
              player_id INTEGER PRIMARY KEY REFERENCES players(telegram_id) ON DELETE CASCADE,
              clan_id INTEGER NOT NULL REFERENCES clans(id) ON DELETE CASCADE,
              role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('leader','officer','member')));
            CREATE TABLE IF NOT EXISTS raid(
              id INTEGER PRIMARY KEY CHECK(id=1), name TEXT NOT NULL, hp INTEGER NOT NULL,
              max_hp INTEGER NOT NULL, cycle INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS raid_hits(
              player_id INTEGER PRIMARY KEY REFERENCES players(telegram_id) ON DELETE CASCADE,
              damage INTEGER NOT NULL DEFAULT 0, hits INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS idx_players_rank ON players(level DESC,xp DESC);
            CREATE INDEX IF NOT EXISTS idx_members_clan ON clan_members(clan_id);
            INSERT OR IGNORE INTO raid(id,name,hp,max_hp) VALUES(1,'World Eater',100000,100000);
            """)

    def close(self) -> None:
        if self.anchor is not None:
            self.anchor.close()
            self.anchor = None
