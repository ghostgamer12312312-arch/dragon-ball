from __future__ import annotations

"""Dragon Ball-themed player exchange with persistent, bounded market prices.

Quotes are integer Zeni values and change on a five-minute market cycle. The
cycle is deterministic per asset, preventing refresh-spam from rerolling prices.
All purchases, sales, fees, stock and holdings are updated atomically.
"""

import math
import random
import time
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .database import Database
from .game import GameError, GameService

TICK_SECONDS = 300
TRADE_FEE_RATE = 0.01
PAGE_SIZE = 6

ASSETS = (
    ("senzu_futures", "Senzu Bean Co.", "🌱", "Senzu beans; steady recovery demand.", 120, 55, 260, 1200),
    ("capsule_corp", "Capsule Corp.", "📦", "Capsule technology and travel gear.", 220, 100, 480, 950),
    ("ki_crystals", "Ki Crystal Mine", "💎", "Refined ki crystals for training.", 175, 70, 400, 1400),
    ("dragon_radar", "Dragon Radar Works", "📡", "Navigation gear for Dragon Ball hunters.", 320, 150, 750, 700),
    ("namekian_orbs", "Namekian Orb Exchange", "🐉", "Rare dragon-orb collectibles.", 950, 420, 2200, 360),
    ("saiyan_armor", "Saiyan Armor Foundry", "🛡️", "Battle armor from the Saiyan frontier.", 540, 240, 1250, 520),
    ("gravity_gym", "Gravity Room Labs", "🪐", "Training equipment for high-gravity worlds.", 410, 180, 900, 600),
    ("scouter_tech", "Scouter Systems", "🔴", "Power-level detection technology.", 280, 120, 650, 820),
    ("kai_planet", "Kai Planet Gardens", "🌿", "Rare medicinal herbs from the Other World.", 360, 160, 800, 640),
    ("fusion_dance", "Metamoran Arts", "💫", "Fusion technique scrolls and accessories.", 780, 330, 1750, 390),
    ("potara_gems", "Potara Gem Trust", "💠", "Collector-grade Potara artifacts.", 1250, 550, 2900, 280),
    ("android_parts", "Red Ribbon Salvage", "⚙️", "Reclaimed android components.", 245, 100, 580, 900),
    ("dino_meat", "Dino Ranchers", "🍖", "Food supplies for long expeditions.", 85, 35, 190, 1600),
    ("space_freight", "Galactic Freight", "🚀", "Interplanetary shipping and logistics.", 305, 135, 690, 760),
    ("frieza_metal", "Frieza Force Metals", "🧊", "Durable alloys from old empire foundries.", 470, 200, 1050, 580),
    ("kaioken_scrolls", "Kaioken Dojo", "📜", "Advanced martial arts instruction.", 625, 275, 1400, 460),
    ("spirit_bomb", "Spirit Energy Co-op", "☀️", "Community-backed energy projects.", 860, 380, 1950, 340),
    ("beerus_dessert", "Beerus Dessert House", "🍮", "Premium sweets with unpredictable demand.", 195, 70, 500, 880),
    ("world_tournament", "World Tournament Group", "🏆", "Event venue, training and broadcast rights.", 390, 170, 880, 660),
    ("time_chamber", "Time Chamber Holdings", "⌛", "Scarce temporal training access contracts.", 1650, 720, 3800, 220),
)


def initialize(db: Database) -> None:
    with db.transaction() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS market_meta(
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), cycle INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS market_assets(
          asset_id TEXT PRIMARY KEY, name TEXT NOT NULL, emoji TEXT NOT NULL,
          description TEXT NOT NULL, base_price INTEGER NOT NULL,
          min_price INTEGER NOT NULL, max_price INTEGER NOT NULL,
          price INTEGER NOT NULL, change_pct REAL NOT NULL DEFAULT 0,
          stock INTEGER NOT NULL, daily_stock INTEGER NOT NULL, stock_day TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS market_positions(
          player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
          asset_id TEXT NOT NULL REFERENCES market_assets(asset_id),
          quantity INTEGER NOT NULL CHECK(quantity>=0), avg_cost REAL NOT NULL CHECK(avg_cost>=0),
          PRIMARY KEY(player_id,asset_id));
        CREATE TABLE IF NOT EXISTS market_transactions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
          asset_id TEXT NOT NULL REFERENCES market_assets(asset_id),
          side TEXT NOT NULL CHECK(side IN ('buy','sell')), quantity INTEGER NOT NULL,
          unit_price INTEGER NOT NULL, fee INTEGER NOT NULL, realized_profit INTEGER NOT NULL DEFAULT 0,
          created_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_market_transactions_player ON market_transactions(player_id,id DESC);
        """)
        day = time.strftime("%Y-%m-%d", time.gmtime())
        cycle = int(time.time()) // TICK_SECONDS
        con.execute("INSERT OR IGNORE INTO market_meta(singleton,cycle) VALUES(1,?)", (cycle,))
        for asset_id, name, emoji, description, base, low, high, stock in ASSETS:
            con.execute("INSERT OR IGNORE INTO market_assets(asset_id,name,emoji,description,base_price,min_price,max_price,price,stock,daily_stock,stock_day) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (asset_id,name,emoji,description,base,low,high,base,stock,stock,day))


def advance_market(con, now: int | None = None) -> None:
    """Apply one bounded deterministic price movement per elapsed five-minute tick."""
    now = int(time.time()) if now is None else int(now)
    target = now // TICK_SECONDS
    current = con.execute("SELECT cycle FROM market_meta WHERE singleton=1").fetchone()[0]
    if target > current:
        # Avoid unbounded catch-up work after very long downtime. One catch-up
        # tick is enough to resume while preserving an observable daily cycle.
        first = max(current + 1, target - 288)
        rows = con.execute("SELECT asset_id,price,min_price,max_price FROM market_assets ORDER BY asset_id").fetchall()
        for cycle in range(first, target + 1):
            for row in rows:
                rng = random.Random(f"db-rpg-market:{row['asset_id']}:{cycle}")
                move = rng.uniform(-0.075, 0.075)
                # Small mean-reversion component limits runaway prices.
                base = next(a[4] for a in ASSETS if a[0] == row["asset_id"])
                deviation = (base - row["price"]) / max(1, base)
                move += max(-0.025, min(0.025, deviation * 0.025))
                old = int(row["price"])
                price = max(int(row["min_price"]), min(int(row["max_price"]), round(old * (1 + move))))
                pct = (price - old) * 100.0 / old if old else 0.0
                con.execute("UPDATE market_assets SET price=?,change_pct=? WHERE asset_id=?", (price,pct,row["asset_id"]))
                row = dict(row)
                row["price"] = price
        con.execute("UPDATE market_meta SET cycle=? WHERE singleton=1", (target,))
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    con.execute("UPDATE market_assets SET stock=daily_stock,stock_day=? WHERE stock_day<>?", (day,day))


def _assets(db: Database, page: int):
    with db.transaction() as con:
        advance_market(con)
        rows = con.execute("SELECT * FROM market_assets ORDER BY asset_id").fetchall()
        total_pages = max(1, math.ceil(len(rows)/PAGE_SIZE))
        page = max(0,min(page,total_pages-1))
        return [dict(r) for r in rows[page*PAGE_SIZE:(page+1)*PAGE_SIZE]], page, total_pages


def _market_screen(rows, page: int, pages: int, zeni: int) -> tuple[str, InlineKeyboardMarkup]:
    lines = ["⚔️ <b>CAPSULE CORP. EXCHANGE</b>",
             f"📊 {len(ASSETS)} Dragon Ball materials · quotes update every 5 min",
             f"💴 Your Zeni: <b>{zeni:,}</b> · trading fee: {TRADE_FEE_RATE:.0%}", ""]
    buttons=[]
    for r in rows:
        icon = "📈" if r["change_pct"] >= 0 else "📉"
        lines.append(f"{r['emoji']} <b>{r['name']}</b> [{r['asset_id'].upper()}]\n💎 {r['price']:,} Zeni {icon} {r['change_pct']:+.1f}% · 📦 {r['stock']:,} left")
        buttons.append([InlineKeyboardButton(f"{r['emoji']} {r['asset_id'].upper()} · {r['price']:,} Zeni",callback_data=f"trade:asset:{r['asset_id']}")])
    lines.append(f"\n📄 Page {page+1}/{pages} · Tap an asset to trade\nBuy low, sell high; prices have risk and can fall.")
    nav=[]
    if page>0: nav.append(InlineKeyboardButton("⬅️ Previous",callback_data=f"trade:page:{page-1}"))
    if page+1<pages: nav.append(InlineKeyboardButton("Next ➡️",callback_data=f"trade:page:{page+1}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton("💼 My Portfolio",callback_data="trade:portfolio")])
    return "\n".join(lines),InlineKeyboardMarkup(buttons)


def portfolio_text(db: Database, player_id: int) -> str:
    with db.transaction() as con:
        advance_market(con)
        rows=con.execute("SELECT p.asset_id,p.quantity,p.avg_cost,a.name,a.emoji,a.price FROM market_positions p JOIN market_assets a ON a.asset_id=p.asset_id WHERE p.player_id=? AND p.quantity>0 ORDER BY a.name",(player_id,)).fetchall()
        if not rows:return "💼 <b>Your Exchange Portfolio</b>\nNo holdings yet. Browse /market and choose a material."
        lines=["💼 <b>YOUR EXCHANGE PORTFOLIO</b>"]
        value=0; basis=0
        for r in rows:
            current=r["quantity"]*r["price"]; cost=round(r["quantity"]*r["avg_cost"])
            change=current-cost; value+=current; basis+=cost
            lines.append(f"{r['emoji']} {r['name']} ×{r['quantity']} · value {current:,} · basis {cost:,} · {'+' if change>=0 else ''}{change:,} Zeni")
        profit=value-basis
        lines.append(f"\nTotal market value: <b>{value:,} Zeni</b>\nUnrealized P/L: <b>{profit:+,} Zeni</b>\nSell quotes include a 1% fee.")
        return "\n".join(lines)


def buy_asset(db: Database, player_id: int, asset_id: str, quantity: int) -> dict:
    if not 1<=quantity<=100: raise GameError("Choose a quantity from 1 to 100.")
    with db.transaction() as con:
        advance_market(con)
        player=con.execute("SELECT coins,banned FROM players WHERE telegram_id=?",(player_id,)).fetchone()
        if player is None: raise GameError("Use /start first to create your fighter profile.")
        if player["banned"]: raise GameError("This account is restricted from game actions.")
        asset=con.execute("SELECT * FROM market_assets WHERE asset_id=?",(asset_id,)).fetchone()
        if asset is None: raise GameError("Unknown exchange asset.")
        if asset["stock"]<quantity: raise GameError(f"Only {asset['stock']} units are currently in stock.")
        subtotal=asset["price"]*quantity; fee=math.ceil(subtotal*TRADE_FEE_RATE); total=subtotal+fee
        if player["coins"]<total: raise GameError(f"You need {total:,} Zeni including the {fee:,} fee.")
        old=con.execute("SELECT quantity,avg_cost FROM market_positions WHERE player_id=? AND asset_id=?",(player_id,asset_id)).fetchone()
        old_qty=int(old["quantity"]) if old else 0
        avg=(old_qty*float(old["avg_cost"])+subtotal+fee)/(old_qty+quantity)
        con.execute("UPDATE players SET coins=coins-? WHERE telegram_id=?",(total,player_id))
        con.execute("UPDATE market_assets SET stock=stock-? WHERE asset_id=?",(quantity,asset_id))
        con.execute("INSERT INTO market_positions(player_id,asset_id,quantity,avg_cost) VALUES(?,?,?,?) ON CONFLICT(player_id,asset_id) DO UPDATE SET quantity=excluded.quantity,avg_cost=excluded.avg_cost",(player_id,asset_id,old_qty+quantity,avg))
        con.execute("INSERT INTO market_transactions(player_id,asset_id,side,quantity,unit_price,fee,created_at) VALUES(?,?,?,?,?,?,?)",(player_id,asset_id,"buy",quantity,asset["price"],fee,int(time.time())))
        return {"name":asset["name"],"quantity":quantity,"unit_price":asset["price"],"subtotal":subtotal,"fee":fee,"total":total,"remaining":player["coins"]-total}


def sell_asset(db: Database, player_id: int, asset_id: str, quantity: int) -> dict:
    if not 1<=quantity<=100: raise GameError("Choose a quantity from 1 to 100.")
    with db.transaction() as con:
        advance_market(con)
        player=con.execute("SELECT coins,banned FROM players WHERE telegram_id=?",(player_id,)).fetchone()
        if player is None: raise GameError("Use /start first to create your fighter profile.")
        if player["banned"]: raise GameError("This account is restricted from game actions.")
        asset=con.execute("SELECT * FROM market_assets WHERE asset_id=?",(asset_id,)).fetchone()
        position=con.execute("SELECT quantity,avg_cost FROM market_positions WHERE player_id=? AND asset_id=?",(player_id,asset_id)).fetchone()
        if asset is None or position is None or position["quantity"]<quantity: raise GameError("You do not own that many units.")
        gross=asset["price"]*quantity; fee=math.ceil(gross*TRADE_FEE_RATE); proceeds=gross-fee
        basis=round(float(position["avg_cost"])*quantity); realized=proceeds-basis
        left=position["quantity"]-quantity
        con.execute("UPDATE players SET coins=coins+? WHERE telegram_id=?",(proceeds,player_id))
        con.execute("UPDATE market_positions SET quantity=? WHERE player_id=? AND asset_id=?",(left,player_id,asset_id))
        con.execute("UPDATE market_assets SET stock=stock+? WHERE asset_id=?",(quantity,asset_id))
        con.execute("INSERT INTO market_transactions(player_id,asset_id,side,quantity,unit_price,fee,realized_profit,created_at) VALUES(?,?,?,?,?,?,?,?)",(player_id,asset_id,"sell",quantity,asset["price"],fee,realized,int(time.time())))
        return {"name":asset["name"],"quantity":quantity,"unit_price":asset["price"],"gross":gross,"fee":fee,"proceeds":proceeds,"realized":realized,"remaining":left}


async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service:GameService=context.application.bot_data["game"]
    user=update.effective_user
    if not user:return
    await service.register(user.id,user.username,user.full_name or "Fighter")
    page=0
    rows,page,pages=await __import__("asyncio").to_thread(_assets,service.db,page)
    player=await __import__("asyncio").to_thread(service.profile,user.id)
    text,markup=_market_screen(rows,page,pages,player["coins"])
    await update.effective_message.reply_text(text,parse_mode="HTML",reply_markup=markup)


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service:GameService=context.application.bot_data["game"]
    user=update.effective_user
    if not user:return
    await service.register(user.id,user.username,user.full_name or "Fighter")
    text=await __import__("asyncio").to_thread(portfolio_text,service.db,user.id)
    await update.effective_message.reply_text(text,parse_mode="HTML")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query=update.callback_query
    await query.answer()
    parts=(query.data or "").split(":")
    service:GameService=context.application.bot_data["game"]
    uid=query.from_user.id
    try:
        await __import__("asyncio").to_thread(service.register,uid,query.from_user.username,query.from_user.full_name or "Fighter")
        if parts[1]=="page":
            rows,page,pages=await __import__("asyncio").to_thread(_assets,service.db,int(parts[2]))
            profile=await __import__("asyncio").to_thread(service.profile,uid)
            text,markup=_market_screen(rows,page,pages,profile["coins"])
            await query.edit_message_text(text,parse_mode="HTML",reply_markup=markup)
        elif parts[1]=="portfolio":
            text=await __import__("asyncio").to_thread(portfolio_text,service.db,uid)
            await query.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Market",callback_data="trade:page:0")]]))
        elif parts[1]=="asset":
            asset_id=parts[2]
            with service.db.transaction() as con:
                advance_market(con)
                a=con.execute("SELECT * FROM market_assets WHERE asset_id=?",(asset_id,)).fetchone()
                pos=con.execute("SELECT quantity FROM market_positions WHERE player_id=? AND asset_id=?",(uid,asset_id)).fetchone()
            if not a: raise GameError("Unknown exchange asset.")
            owned=pos["quantity"] if pos else 0
            direction="📈" if a["change_pct"]>=0 else "📉"
            text=(f"{a['emoji']} <b>{a['name']}</b> [{a['asset_id'].upper()}]\n{a['description']}\n\n"
                  f"💎 Quote: <b>{a['price']:,} Zeni</b> {direction} {a['change_pct']:+.1f}%\n"
                  f"📦 Supply: {a['stock']:,} · You own: {owned}\n"
                  f"Trading fee: {TRADE_FEE_RATE:.0%}. Prices can rise or fall; profit is not guaranteed.")
            buttons=[]
            for qty in (1,5,10):
                if qty<=a["stock"]: buttons.append(InlineKeyboardButton(f"Buy ×{qty}",callback_data=f"trade:buy:{asset_id}:{qty}"))
            if owned:
                for qty in sorted(set((1,min(5,owned),min(10,owned),owned))):
                    if qty: buttons.append(InlineKeyboardButton(f"Sell ×{qty}",callback_data=f"trade:sell:{asset_id}:{qty}"))
            keyboard=[buttons[i:i+2] for i in range(0,len(buttons),2)]
            keyboard.append([InlineKeyboardButton("⬅️ Exchange",callback_data="trade:page:0")])
            await query.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(keyboard))
        elif parts[1] in {"buy","sell"}:
            side,asset_id,qty=parts[1],parts[2],int(parts[3])
            if side=="buy":
                result=await __import__("asyncio").to_thread(buy_asset,service.db,uid,asset_id,qty)
                text=f"✅ Purchased {result['quantity']} × {result['name']} at {result['unit_price']:,} Zeni each.\nTotal {result['total']:,} (includes {result['fee']:,} fee). Remaining: {result['remaining']:,} Zeni.\nThe asset is now in your portfolio; its quote changes every five minutes. Its value may rise or fall."
            else:
                result=await __import__("asyncio").to_thread(sell_asset,service.db,uid,asset_id,qty)
                text=f"✅ Sold {result['quantity']} × {result['name']} at {result['unit_price']:,} Zeni each.\nProceeds {result['proceeds']:,} (after {result['fee']:,} fee). Realized P/L: {result['realized']:+,} Zeni."
            await query.edit_message_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Exchange",callback_data="trade:page:0"),InlineKeyboardButton("Portfolio",callback_data="trade:portfolio")]]))
    except (GameError,ValueError) as exc:
        await query.edit_message_text(str(exc))
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Market callback failed")
        await query.edit_message_text("Trade could not be completed. Please refresh the exchange and retry.")


def register(application: Application, db: Database) -> None:
    initialize(db)
    application.add_handler(CommandHandler("market",market_command))
    application.add_handler(CommandHandler("portfolio",portfolio_command))
    application.add_handler(CallbackQueryHandler(callback,pattern=r"^trade:"))
