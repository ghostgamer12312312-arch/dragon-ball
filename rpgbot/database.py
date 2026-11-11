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
import aiosqlite
from pathlib import Path


class Database:
    def __init__(self, path: str):
        self.path = path
        self._anchor = None
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        db = await aiosqlite.connect(self.path, timeout=20)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA busy_timeout = 20000")
        if self.path != ":memory:":
            await db.execute("PRAGMA journal_mode = WAL")
        return db

    async def initialize(self):
        if self.path == ":memory:" and self._anchor is None:
            self._anchor = await aiosqlite.connect("file:rpg_shared?mode=memory&cache=shared", uri=True)
            self.path = "file:rpg_shared?mode=memory&cache=shared"

        db = await self.connect()
        try:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS players(
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT NOT NULL,
                coins INTEGER NOT NULL DEFAULT 100 CHECK(coins >= 0),
                gems INTEGER NOT NULL DEFAULT 0 CHECK(gems >= 0),
                level INTEGER NOT NULL DEFAULT 1 CHECK(level >= 1),
                xp INTEGER NOT NULL DEFAULT 0 CHECK(xp >= 0),
                energy INTEGER NOT NULL DEFAULT 100 CHECK(energy >= 0),
                max_energy INTEGER NOT NULL DEFAULT 100 CHECK(max_energy >= 1),
                active_character TEXT NOT NULL DEFAULT 'goku',
                region TEXT NOT NULL DEFAULT 'earth',
                daily_streak INTEGER NOT NULL DEFAULT 0,
                last_daily TEXT,
                banned INTEGER NOT NULL DEFAULT 0,
                explores INTEGER NOT NULL DEFAULT 0,
                pve_wins INTEGER NOT NULL DEFAULT 0,
                pvp_wins INTEGER NOT NULL DEFAULT 0,
                str_stat INTEGER NOT NULL DEFAULT 5,
                agi_stat INTEGER NOT NULL DEFAULT 5,
                int_stat INTEGER NOT NULL DEFAULT 5,
                vit_stat INTEGER NOT NULL DEFAULT 5,
                luk_stat INTEGER NOT NULL DEFAULT 5,
                stat_points INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS market_meta(
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                cycle INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS market_assets(
                asset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL,
                description TEXT NOT NULL,
                base_price INTEGER NOT NULL,
                min_price INTEGER NOT NULL,
                max_price INTEGER NOT NULL,
                price INTEGER NOT NULL,
                change_pct REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0,
                daily_stock INTEGER NOT NULL DEFAULT 0,
                stock_day TEXT
            );

            CREATE TABLE IF NOT EXISTS market_positions(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                asset_id TEXT NOT NULL REFERENCES market_assets(asset_id) ON DELETE CASCADE,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                avg_cost REAL NOT NULL DEFAULT 0,
                PRIMARY KEY(player_id, asset_id)
            );

            CREATE TABLE IF NOT EXISTS market_transactions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                asset_id TEXT NOT NULL REFERENCES market_assets(asset_id),
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price INTEGER NOT NULL,
                fee INTEGER NOT NULL,
                realized_profit INTEGER,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS owned_characters(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                character_id TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                shards INTEGER NOT NULL DEFAULT 0,
                equipped INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(player_id, character_id)
            );

            CREATE TABLE IF NOT EXISTS owned_items(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                PRIMARY KEY(player_id, item_id)
            );

            CREATE TABLE IF NOT EXISTS owned_skills(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                skill_id TEXT NOT NULL,
                slot INTEGER,
                PRIMARY KEY(player_id, skill_id)
            );

            CREATE TABLE IF NOT EXISTS owned_pets(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                pet_id TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                equipped INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(player_id, pet_id)
            );

            CREATE TABLE IF NOT EXISTS clans(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                leader_id INTEGER NOT NULL REFERENCES players(telegram_id),
                treasury INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS clan_members(
                player_id INTEGER PRIMARY KEY REFERENCES players(telegram_id) ON DELETE CASCADE,
                clan_id INTEGER NOT NULL REFERENCES clans(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'member',
                joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS active_battles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                enemy TEXT NOT NULL,
                enemy_hp INTEGER NOT NULL,
                enemy_max_hp INTEGER NOT NULL,
                player_hp INTEGER NOT NULL,
                player_max_hp INTEGER NOT NULL,
                mp INTEGER NOT NULL DEFAULT 100,
                ult INTEGER NOT NULL DEFAULT 0,
                transformed INTEGER NOT NULL DEFAULT 0,
                turn INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS game_content(
                kind TEXT NOT NULL,
                content_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY(kind, content_id)
            );

            CREATE TABLE IF NOT EXISTS custom_art(
                entity_key TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                uploaded_by INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS player_quests(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                day TEXT NOT NULL,
                quest_id TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                claimed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(player_id, day, quest_id)
            );

            CREATE TABLE IF NOT EXISTS dragon_balls(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                star INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(player_id, star)
            );

            CREATE TABLE IF NOT EXISTS market_listings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_id INTEGER,
                details TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_players_rank ON players(level DESC, xp DESC);
            CREATE INDEX IF NOT EXISTS idx_market_listings_status ON market_listings(status, id DESC);
            CREATE INDEX IF NOT EXISTS idx_battles_player ON active_battles(player_id, status);
            CREATE INDEX IF NOT EXISTS idx_members_clan ON clan_members(clan_id);
            """)

            await self._seed_market(db)
            await db.commit()
        finally:
            await db.close()

    async def _seed_market(self, db):
        try:
            from .market_service import ASSETS
        except ImportError:
            ASSETS = []

        import time
        from datetime import UTC, datetime

        if not ASSETS:
            return

        cycle = int(time.time()) // 300
        day = datetime.now(UTC).date().isoformat()
        await db.execute("INSERT OR IGNORE INTO market_meta(singleton, cycle) VALUES(1, ?)", (cycle,))
        for asset in ASSETS:
            asset_id, name, emoji, description, base_price, min_price, max_price, stock = asset
            await db.execute(
                "INSERT OR IGNORE INTO market_assets(asset_id, name, emoji, description, base_price, min_price, max_price, price, stock, daily_stock, stock_day) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (asset_id, name, emoji, description, base_price, min_price, max_price, base_price, stock, stock, day),
            )

    async def close(self):
        if self._anchor is not None:
            await self._anchor.close()
            self._anchor = None
