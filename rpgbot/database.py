from __future__ import annotations

import aiosqlite
from pathlib import Path


class Database:
    """Async SQLite store. Each operation owns its connection and transaction."""

    def __init__(self, path: str):
        self.path = path
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
        db = await self.connect()
        try:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS players(
              telegram_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT NOT NULL,
              coins INTEGER NOT NULL DEFAULT 100 CHECK(coins>=0), level INTEGER NOT NULL DEFAULT 1 CHECK(level>=1),
              xp INTEGER NOT NULL DEFAULT 0 CHECK(xp>=0), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS market_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),cycle INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS market_assets(
              asset_id TEXT PRIMARY KEY,name TEXT NOT NULL,emoji TEXT NOT NULL,description TEXT NOT NULL,
              base_price INTEGER NOT NULL,min_price INTEGER NOT NULL,max_price INTEGER NOT NULL,
              price INTEGER NOT NULL,change_pct REAL NOT NULL DEFAULT 0,stock INTEGER NOT NULL,
              daily_stock INTEGER NOT NULL,stock_day TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS market_positions(
              player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
              asset_id TEXT NOT NULL REFERENCES market_assets(asset_id),quantity INTEGER NOT NULL CHECK(quantity>=0),
              avg_cost REAL NOT NULL CHECK(avg_cost>=0),PRIMARY KEY(player_id,asset_id));
            CREATE TABLE IF NOT EXISTS market_transactions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,player_id INTEGER NOT NULL REFERENCES players(telegram_id),
              asset_id TEXT NOT NULL REFERENCES market_assets(asset_id),side TEXT NOT NULL CHECK(side IN ('buy','sell')),
              quantity INTEGER NOT NULL,unit_price INTEGER NOT NULL,fee INTEGER NOT NULL,realized_profit INTEGER NOT NULL DEFAULT 0,
              created_at INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_market_transactions_player ON market_transactions(player_id,id DESC);
            CREATE TABLE IF NOT EXISTS active_battles(
              id INTEGER PRIMARY KEY AUTOINCREMENT,player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
              enemy TEXT NOT NULL,enemy_hp INTEGER NOT NULL,player_hp INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'active',turn INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS custom_art(
              entity_key TEXT PRIMARY KEY,file_id TEXT NOT NULL,uploaded_by INTEGER NOT NULL,updated_at INTEGER NOT NULL);
            """)
            await db.commit()
            await seed_assets(db)
        finally:
            await db.close()


ASSETS = (
    ("senzu_futures","Senzu Bean Co.","🌱","Senzu beans and recovery supplies",120,55,260,1200),
    ("capsule_corp","Capsule Corp.","📦","Capsule technology and travel gear",220,100,480,950),
    ("ki_crystals","Ki Crystal Mine","💎","Refined ki crystals for training",175,70,400,1400),
    ("dragon_radar","Dragon Radar Works","📡","Navigation equipment for dragon-ball hunters",320,150,750,700),
    ("namek_orbs","Namekian Orb Exchange","🐉","Rare Namekian collectibles",950,420,2200,360),
    ("saiyan_armor","Saiyan Armor Foundry","🛡️","Battle armor from the Saiyan frontier",540,240,1250,520),
    ("gravity_gym","Gravity Room Labs","🪐","High-gravity training equipment",410,180,900,600),
    ("scouter_tech","Scouter Systems","🔴","Power-level detection technology",280,120,650,820),
    ("kai_gardens","Kai Planet Gardens","🌿","Medicinal herbs from the Other World",360,160,800,640),
    ("fusion_arts","Metamoran Arts","💫","Fusion technique scrolls and accessories",780,330,1750,390),
    ("potara_gems","Potara Gem Trust","💠","Collector-grade Potara artifacts",1250,550,2900,280),
    ("android_parts","Red Ribbon Salvage","⚙️","Reclaimed android components",245,100,580,900),
    ("dino_meat","Dino Ranchers","🍖","Food supplies for expeditions",85,35,190,1600),
    ("space_freight","Galactic Freight","🚀","Interplanetary shipping and logistics",305,135,690,760),
    ("frieza_metal","Frieza Force Metals","🧊","Durable alloys from old empire foundries",470,200,1050,580),
    ("kaioken_scrolls","Kaioken Dojo","📜","Advanced martial arts instruction",625,275,1400,460),
    ("spirit_energy","Spirit Energy Co-op","☀️","Community-backed energy projects",860,380,1950,340),
    ("beerus_dessert","Beerus Dessert House","🍮","Premium sweets with unpredictable demand",195,70,500,880),
    ("world_tournament","World Tournament Group","🏆","Event venue and broadcast rights",390,170,880,660),
    ("time_chamber","Time Chamber Holdings","⌛","Scarce temporal training contracts",1650,720,3800,220),
)


async def seed_assets(db):
    import time
    from datetime import UTC, datetime
    cycle = int(time.time()) // 300
    day = datetime.now(UTC).date().isoformat()
    await db.execute("BEGIN IMMEDIATE")
    try:
        await db.execute("INSERT OR IGNORE INTO market_meta(singleton,cycle) VALUES(1,?)", (cycle,))
        for asset in ASSETS:
            asset_id,name,emoji,description,base,low,high,stock=asset
            await db.execute("INSERT OR IGNORE INTO market_assets(asset_id,name,emoji,description,base_price,min_price,max_price,price,stock,daily_stock,stock_day) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                             (asset_id,name,emoji,description,base,low,high,base,stock,stock,day))
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    async def close(self):
        return None
