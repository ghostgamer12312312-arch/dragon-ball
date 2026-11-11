from __future__ import annotations

import aiosqlite
from pathlib import Path


class Database:
    """Async SQLite persistence. Existing player and market data are preserved."""

    def __init__(self, path: str):
        self.path = path
        self._anchor = None
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        db = await aiosqlite.connect(self.path, timeout=20)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=20000")
        if self.path != ":memory:":
            await db.execute("PRAGMA journal_mode=WAL")
        return db

    async def initialize(self):
        # A persistent shared-memory connection makes :memory: useful in tests.
        if self.path == ":memory:" and self._anchor is None:
            self._anchor = await aiosqlite.connect("file:rpg-shared?mode=memory&cache=shared", uri=True)
            self.path = "file:rpg-shared?mode=memory&cache=shared"
        db = await self.connect()
        try:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS players(
              telegram_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT NOT NULL,
              coins INTEGER NOT NULL DEFAULT 100 CHECK(coins>=0), level INTEGER NOT NULL DEFAULT 1 CHECK(level>=1),
              xp INTEGER NOT NULL DEFAULT 0 CHECK(xp>=0), gems INTEGER NOT NULL DEFAULT 0 CHECK(gems>=0),
              energy INTEGER NOT NULL DEFAULT 100 CHECK(energy>=0), max_energy INTEGER NOT NULL DEFAULT 100 CHECK(max_energy>=1),
              active_character TEXT NOT NULL DEFAULT 'goku', region TEXT NOT NULL DEFAULT 'earth',
              daily_streak INTEGER NOT NULL DEFAULT 0, last_daily TEXT, banned INTEGER NOT NULL DEFAULT 0,
              explores INTEGER NOT NULL DEFAULT 0, pve_wins INTEGER NOT NULL DEFAULT 0, pvp_wins INTEGER NOT NULL DEFAULT 0,
              str_stat INTEGER NOT NULL DEFAULT 5, agi_stat INTEGER NOT NULL DEFAULT 5, int_stat INTEGER NOT NULL DEFAULT 5,
              vit_stat INTEGER NOT NULL DEFAULT 5, luk_stat INTEGER NOT NULL DEFAULT 5,
              stat_points INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL DEFAULT '',
              settings_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS market_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),cycle INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS market_assets(asset_id TEXT PRIMARY KEY,name TEXT NOT NULL,emoji TEXT NOT NULL,description TEXT NOT NULL,base_price INTEGER NOT NULL,min_price INTEGER NOT NULL,max_price INTEGER NOT NULL,price INTEGER NOT NULL,change_pct REAL NOT NULL DEFAULT 0,stock INTEGER NOT NULL,daily_stock INTEGER NOT NULL,stock_day TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS market_positions(player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,asset_id TEXT NOT NULL REFERENCES market_assets(asset_id),quantity INTEGER NOT NULL CHECK(quantity>=0),avg_cost REAL NOT NULL CHECK(avg_cost>=0),PRIMARY KEY(player_id,asset_id));
            CREATE TABLE IF NOT EXISTS market_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,player_id INTEGER NOT NULL REFERENCES players(telegram_id),asset_id TEXT NOT NULL REFERENCES market_assets(asset_id),side TEXT NOT NULL CHECK(side IN ('buy','sell')),quantity INTEGER NOT NULL,unit_price INTEGER NOT NULL,fee INTEGER NOT NULL,realized_profit INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS owned_characters(player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,character_id TEXT NOT NULL,level INTEGER NOT NULL DEFAULT 1,shards INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(player_id,character_id));
            CREATE TABLE IF NOT EXISTS owned_items(player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,item_id TEXT NOT NULL,quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),enhancement INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(player_id,item_id));
            CREATE TABLE IF NOT EXISTS owned_skills(player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,skill_id TEXT NOT NULL,slot INTEGER,PRIMARY KEY(player_id,skill_id));
            CREATE TABLE IF NOT EXISTS owned_pets(player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,pet_id TEXT NOT NULL,level INTEGER NOT NULL DEFAULT 1,equipped INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(player_id,pet_id));
            CREATE TABLE IF NOT EXISTS clans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE COLLATE NOCASE,leader_id INTEGER NOT NULL REFERENCES players(telegram_id),treasury INTEGER NOT NULL DEFAULT 0,xp INTEGER NOT NULL DEFAULT 0,level INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS clan_members(player_id INTEGER PRIMARY KEY REFERENCES players(telegram_id) ON DELETE CASCADE,clan_id INTEGER NOT NULL REFERENCES clans(id) ON DELETE CASCADE,role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('leader','officer','member')));
            CREATE TABLE IF NOT EXISTS clan_raids(id INTEGER PRIMARY KEY AUTOINCREMENT,clan_id INTEGER NOT NULL REFERENCES clans(id) ON DELETE CASCADE,boss TEXT NOT NULL,hp INTEGER NOT NULL,max_hp INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'active',started_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS active_battles(id INTEGER PRIMARY KEY AUTOINCREMENT,player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,kind TEXT NOT NULL,enemy TEXT NOT NULL,enemy_hp INTEGER NOT NULL,enemy_max_hp INTEGER NOT NULL,player_hp INTEGER NOT NULL,player_max_hp INTEGER NOT NULL,mp INTEGER NOT NULL DEFAULT 100,ult INTEGER NOT NULL DEFAULT 0,transformed INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'active',turn INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS custom_art(entity_key TEXT PRIMARY KEY,file_id TEXT NOT NULL,uploaded_by INTEGER NOT NULL,updated_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS player_quests(player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,day TEXT NOT NULL,quest_id TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,claimed INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(player_id,day,quest_id));
            CREATE TABLE IF NOT EXISTS dragon_balls(player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,star INTEGER NOT NULL,quantity INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(player_id,star));
            CREATE TABLE IF NOT EXISTS market_listings(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER NOT NULL REFERENCES players(telegram_id),item_id TEXT NOT NULL,quantity INTEGER NOT NULL,price INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'active',created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,actor_id INTEGER NOT NULL,action TEXT NOT NULL,target_id INTEGER,details TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_players_rank ON players(level DESC,xp DESC);
            CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(clan_id);
            CREATE INDEX IF NOT EXISTS idx_market_listings_status ON market_listings(status,id DESC);
            CREATE INDEX IF NOT EXISTS idx_battles_player ON active_battles(player_id,status);
            """)
            # Non-destructive schema additions for databases created by earlier versions.
            cur = await db.execute("PRAGMA table_info(players)")
            existing = {r["name"] for r in await cur.fetchall()}
            additions = {
                "gems": "INTEGER NOT NULL DEFAULT 0", "energy": "INTEGER NOT NULL DEFAULT 100",
                "max_energy": "INTEGER NOT NULL DEFAULT 100", "active_character": "TEXT NOT NULL DEFAULT 'goku'",
                "region": "TEXT NOT NULL DEFAULT 'earth'", "daily_streak": "INTEGER NOT NULL DEFAULT 0",
                "last_daily": "TEXT", "banned": "INTEGER NOT NULL DEFAULT 0", "explores": "INTEGER NOT NULL DEFAULT 0",
                "pve_wins": "INTEGER NOT NULL DEFAULT 0", "pvp_wins": "INTEGER NOT NULL DEFAULT 0",
                "str_stat": "INTEGER NOT NULL DEFAULT 5", "agi_stat": "INTEGER NOT NULL DEFAULT 5",
                "int_stat": "INTEGER NOT NULL DEFAULT 5", "vit_stat": "INTEGER NOT NULL DEFAULT 5",
                "luk_stat": "INTEGER NOT NULL DEFAULT 5", "stat_points": "INTEGER NOT NULL DEFAULT 0",
                "title": "TEXT NOT NULL DEFAULT ''", "settings_json": "TEXT NOT NULL DEFAULT '{}'",
            }
            for col, definition in additions.items():
                if col not in existing:
                    await db.execute(f"ALTER TABLE players ADD COLUMN {col} {definition}")
            await db.commit()
            await self._seed_market(db)
        finally:
            await db.close()

    async def _seed_market(self, db):
        from .market_service import ASSETS
        import time
        from datetime import UTC, datetime
        cycle=int(time.time())//300
        day=datetime.now(UTC).date().isoformat()
        await db.execute("INSERT OR IGNORE INTO market_meta(singleton,cycle) VALUES(1,?)",(cycle,))
        for asset in ASSETS:
            asset_id,name,emoji,description,base,low,high,stock=asset
            await db.execute("INSERT OR IGNORE INTO market_assets(asset_id,name,emoji,description,base_price,min_price,max_price,price,stock,daily_stock,stock_day) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(asset_id,name,emoji,description,base,low,high,base,stock,stock,day))
        await db.commit()

    async def close(self):
        if self._anchor is not None:
            await self._anchor.close()
            self._anchor=None
