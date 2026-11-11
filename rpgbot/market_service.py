from __future__ import annotations

import math
import random
import time
from datetime import UTC, datetime

from .database import Database

# Fictional game assets; no real-world securities or monetary value.
ASSETS = [
    ("senzu_futures", "Senzu Bean Co.", "🌱", "Rare healing bean supply", 180, 90, 360, 40),
    ("capsule_corp", "Capsule Corp. Capsules", "💊", "Compact technology materials", 240, 120, 480, 35),
    ("ki_crystals", "Ki Crystals", "💎", "Refined training crystals", 320, 160, 640, 30),
    ("namekian_water", "Namekian Sacred Water", "💧", "A scarce restorative", 420, 210, 840, 24),
    ("dragon_radar", "Dragon Radar Parts", "📡", "Navigation device components", 500, 250, 1000, 20),
    ("gravity_ore", "Gravity Ore", "🪨", "Heavy training material", 620, 310, 1240, 18),
    ("zenkai_cells", "Zenkai Cells", "🧬", "Rare recovery research stock", 760, 380, 1520, 16),
    ("scouter_lenses", "Scouter Lenses", "🔭", "Recon equipment parts", 900, 450, 1800, 14),
    ("kai_seeds", "Kai Seeds", "🌰", "Mystic cultivation seed", 1100, 550, 2200, 12),
    ("spirit_crystal", "Spirit Crystals", "✨", "Concentrated spirit energy", 1350, 675, 2700, 10),
    ("time_chamber", "Time Chamber Permits", "⏳", "Limited training access token", 1600, 800, 3200, 9),
    ("majin_seals", "Majin Seals", "🔱", "Unusual arcane material", 1900, 950, 3800, 8),
    ("kai_tokens", "Supreme Kai Tokens", "🪙", "Exchangeable event tokens", 2300, 1150, 4600, 7),
    ("pod_fuel", "Saiyan Pod Fuel", "🚀", "Interplanetary travel fuel", 2800, 1400, 5600, 6),
    ("world_tree", "World Tree Sap", "🌳", "Premium crafting ingredient", 3400, 1700, 6800, 5),
    ("dragon_scale", "Dragon Scales", "🐉", "Rare collectible material", 4200, 2100, 8400, 4),
    ("god_ki", "God Ki Infusions", "🔥", "High-tier training essence", 5200, 2600, 10400, 3),
    ("wish_orbs", "Wish Orb Fragments", "🔮", "Uncommon wish-system fragments", 6500, 3250, 13000, 2),
]
TICK_SECONDS = 300
TRADE_FEE_RATE = 0.01
PAGE_SIZE = 6

class GameError(ValueError):
    """Expected, player-safe game rule error."""

async def advance_market(con, now: int | None = None):
    now = int(time.time()) if now is None else int(now)
    target = now // TICK_SECONDS
    cur = await con.execute("SELECT cycle FROM market_meta WHERE singleton=1")
    row = await cur.fetchone()
    current = row[0] if row else target
    if target > current:
        first = max(current + 1, target - 288)
        cur = await con.execute("SELECT asset_id,price,min_price,max_price FROM market_assets ORDER BY asset_id")
        rows = [dict(r) for r in await cur.fetchall()]
        bases = {a[0]: a[4] for a in ASSETS}
        for tick in range(first, target + 1):
            for asset in rows:
                rng = random.Random(f"dragon-ball-exchange:{asset['asset_id']}:{tick}")
                change = rng.uniform(-0.075, 0.075)
                base = bases.get(asset["asset_id"], asset["price"])
                change += max(-0.025, min(0.025, (base - asset["price"]) / base * 0.025))
                old = asset["price"]
                price = max(asset["min_price"], min(asset["max_price"], round(old * (1 + change))))
                pct = (price - old) * 100 / old if old else 0
                await con.execute("UPDATE market_assets SET price=?,change_pct=? WHERE asset_id=?", (price, pct, asset["asset_id"]))
                asset["price"] = price
        await con.execute("UPDATE market_meta SET cycle=? WHERE singleton=1", (target,))
    day = datetime.fromtimestamp(now, UTC).date().isoformat()
    await con.execute("UPDATE market_assets SET stock=daily_stock,stock_day=? WHERE stock_day<>?", (day, day))

async def market_page(db: Database, page: int = 0):
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await advance_market(con)
        rows = [dict(r) for r in await (await con.execute("SELECT * FROM market_assets ORDER BY asset_id")).fetchall()]
        pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
        page = max(0, min(page, pages - 1))
        await con.commit()
        return rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], page, pages
    except Exception:
        await con.rollback()
        raise
    finally:
        await con.close()

async def buy_asset(db: Database, user_id: int, asset_id: str, quantity: int):
    if not 1 <= quantity <= 100: raise GameError("Choose a quantity from 1 to 100.")
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await advance_market(con)
        p = await (await con.execute("SELECT coins FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        a = await (await con.execute("SELECT * FROM market_assets WHERE asset_id=?", (asset_id,))).fetchone()
        if not p: raise GameError("Use /start before trading.")
        if not a: raise GameError("Unknown exchange asset.")
        if a["stock"] < quantity: raise GameError(f"Only {a['stock']} units remain in stock.")
        subtotal = a["price"] * quantity
        fee = math.ceil(subtotal * TRADE_FEE_RATE)
        total = subtotal + fee
        if p["coins"] < total: raise GameError(f"You need {total:,} Zeni including the {fee:,} fee.")
        old = await (await con.execute("SELECT quantity,avg_cost FROM market_positions WHERE player_id=? AND asset_id=?", (user_id, asset_id))).fetchone()
        count = int(old["quantity"]) if old else 0
        average = (count * float(old["avg_cost"]) + total) / (count + quantity)
        await con.execute("UPDATE players SET coins=coins-? WHERE telegram_id=?", (total, user_id))
        await con.execute("UPDATE market_assets SET stock=stock-? WHERE asset_id=?", (quantity, asset_id))
        await con.execute("INSERT INTO market_positions(player_id,asset_id,quantity,avg_cost) VALUES(?,?,?,?) ON CONFLICT(player_id,asset_id) DO UPDATE SET quantity=excluded.quantity,avg_cost=excluded.avg_cost", (user_id, asset_id, count + quantity, average))
        await con.execute("INSERT INTO market_transactions(player_id,asset_id,side,quantity,unit_price,fee,created_at) VALUES(?,?,?,?,?,?,?)", (user_id, asset_id, "buy", quantity, a["price"], fee, now := int(time.time())))
        await con.commit()
        return {"name": a["name"], "quantity": quantity, "unit_price": a["price"], "fee": fee, "total": total, "coins_left": p["coins"] - total}
    except Exception:
        await con.rollback()
        raise
    finally:
        await con.close()

async def sell_asset(db: Database, user_id: int, asset_id: str, quantity: int):
    if not 1 <= quantity <= 100: raise GameError("Choose a quantity from 1 to 100.")
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await advance_market(con)
        a = await (await con.execute("SELECT * FROM market_assets WHERE asset_id=?", (asset_id,))).fetchone()
        pos = await (await con.execute("SELECT quantity,avg_cost FROM market_positions WHERE player_id=? AND asset_id=?", (user_id, asset_id))).fetchone()
        if not a or not pos or pos["quantity"] < quantity: raise GameError("You do not own that many units.")
        gross = a["price"] * quantity
        fee = math.ceil(gross * TRADE_FEE_RATE)
        proceeds = gross - fee
        realized = proceeds - round(float(pos["avg_cost"]) * quantity)
        left = pos["quantity"] - quantity
        await con.execute("UPDATE players SET coins=coins+? WHERE telegram_id=?", (proceeds, user_id))
        await con.execute("UPDATE market_positions SET quantity=? WHERE player_id=? AND asset_id=?", (left, user_id, asset_id))
        await con.execute("UPDATE market_assets SET stock=stock+? WHERE asset_id=?", (quantity, asset_id))
        await con.execute("INSERT INTO market_transactions(player_id,asset_id,side,quantity,unit_price,fee,realized_profit,created_at) VALUES(?,?,?,?,?,?,?,?)", (user_id, asset_id, "sell", quantity, a["price"], fee, realized, int(time.time())))
        await con.commit()
        return {"name": a["name"], "quantity": quantity, "unit_price": a["price"], "fee": fee, "proceeds": proceeds, "realized": realized}
    except Exception:
        await con.rollback()
        raise
    finally:
        await con.close()

async def portfolio(db: Database, user_id: int):
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await advance_market(con)
        rows = [dict(r) for r in await (await con.execute("SELECT p.asset_id,p.quantity,p.avg_cost,a.name,a.emoji,a.price FROM market_positions p JOIN market_assets a ON a.asset_id=p.asset_id WHERE p.player_id=? AND p.quantity>0 ORDER BY a.name", (user_id,))).fetchall()]
        await con.commit()
        if not rows: return "💼 <b>YOUR CAPSULE CORP. PORTFOLIO</b>\nNo holdings yet. Open /market and choose an asset."
        lines = ["💼 <b>YOUR CAPSULE CORP. PORTFOLIO</b>"]
        value = basis = 0
        for r in rows:
            current = r["quantity"] * r["price"]
            cost = round(r["quantity"] * r["avg_cost"])
            value += current; basis += cost
            lines.append(f"{r['emoji']} {r['name']} ×{r['quantity']} · value {current:,} · basis {cost:,} · P/L {current-cost:+,} Zeni")
        lines.append(f"\nValue: <b>{value:,} Zeni</b> · unrealized P/L: <b>{value-basis:+,} Zeni</b>\nPrices can rise or fall.")
        return "\n".join(lines)
    finally:
        await con.close()
