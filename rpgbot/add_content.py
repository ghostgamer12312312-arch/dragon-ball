from __future__ import annotations

import json
import re
import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .config import Settings
from .database import Database
from .game import GameError

SCHEMAS: dict[str, tuple[str, ...]] = {
    "item": ("name", "description", "price", "effect", "amount"),
    "character": ("name", "series", "rank", "rarity", "element", "trait", "ability", "hp", "attack"),
    "skill": ("name", "power", "mp_cost", "cooldown", "kind"),
    "enemy": ("name", "hp", "attack", "coins", "xp"),
    "boss": ("name", "hp", "attack", "coins", "xp", "region"),
    "pet": ("name", "rarity", "bonus", "price"), "region": ("name", "weather", "level", "description"),
    "gear": ("name", "slot", "attack", "defense", "rarity"), "recipe": ("name", "output", "materials", "quantity"),
    "banner": ("name", "price", "featured"), "title": ("name", "description"), "quest": ("name", "action", "goal", "coins", "xp"),
    "dungeon": ("name", "region", "floors", "difficulty", "reward"),
    "market_asset": ("name", "emoji", "description", "price", "min_price", "max_price", "stock"),
    "custom": ("category", "name", "description", "data_json"),
}
NUMERIC = {"price", "amount", "rarity", "hp", "attack", "power", "mp_cost", "cooldown", "coins", "xp", "level", "defense", "quantity", "goal", "floors", "reward", "min_price", "max_price", "stock"}
GRANT_LIMITS = {"coins": 1_000_000, "gems": 100_000, "xp": 10_000_000, "level": 10_000, "energy": 100_000, "stat_points": 100_000}


def content_id(value: str) -> str:
    key = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")
    if not key or len(key) > 48: raise GameError("ID must contain 1–48 letters, numbers, or underscores.")
    return key

def parse_values(kind: str, raw: str) -> tuple[str, dict[str, Any]]:
    fields = SCHEMAS.get(kind)
    if fields is None: raise GameError("Unknown content type. Use /add to see available types.")
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != len(fields) + 1: raise GameError(f"Usage fields for {kind}: ID|" + "|".join(fields))
    key = content_id(parts[0]); payload: dict[str, Any] = {}
    for field, value in zip(fields, parts[1:]):
        if not value: raise GameError(f"{field} cannot be empty.")
        if field in NUMERIC:
            try: payload[field] = int(value)
            except ValueError as exc: raise GameError(f"{field} must be a whole number.") from exc
        elif field == "data_json":
            if len(value) > 2000: raise GameError("data_json is limited to 2,000 characters.")
            try: parsed = json.loads(value)
            except json.JSONDecodeError as exc: raise GameError("data_json must be valid JSON.") from exc
            if not isinstance(parsed, dict): raise GameError("data_json must be a JSON object.")
            payload[field] = parsed
        else: payload[field] = value[:240]
    for field, number in payload.items():
        if field in NUMERIC and number < 0: raise GameError(f"{field} cannot be negative.")
    for field in ("price", "hp", "goal", "floors", "quantity", "stock"):
        if field in payload and payload[field] < 1: raise GameError(f"{field} must be at least 1.")
    if "min_price" in payload and payload["min_price"] > payload["max_price"]: raise GameError("min_price cannot exceed max_price.")
    if "rank" in payload and payload["rank"].upper() not in {"Z", "S", "A", "B", "E"}: raise GameError("rank must be Z, S, A, B, or E.")
    if "rarity" in payload:
        rarity = payload["rarity"]
        allowed = {"common", "uncommon", "rare", "epic", "legendary", "mythic", "mythical", "omni"}
        if (isinstance(rarity, int) and not 1 <= rarity <= 5) or (isinstance(rarity, str) and rarity.lower() not in allowed):
            raise GameError("rarity must be 1–5 or a recognized rarity name.")
    return key, payload

async def initialize_content(db: Database) -> None:
    con = await db.connect()
    try:
        await con.execute("CREATE TABLE IF NOT EXISTS game_content(kind TEXT NOT NULL,content_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_by INTEGER NOT NULL,created_at INTEGER NOT NULL,PRIMARY KEY(kind,content_id))")
        await con.commit()
    finally: await con.close()

async def save_content(db: Database, kind: str, key: str, payload: dict[str, Any], actor: int) -> None:
    if kind not in SCHEMAS: raise GameError("Unsupported content type.")
    await initialize_content(db); con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute("INSERT INTO game_content VALUES(?,?,?,?,?) ON CONFLICT(kind,content_id) DO UPDATE SET payload_json=excluded.payload_json,created_by=excluded.created_by,created_at=excluded.created_at", (kind, key, json.dumps(payload, ensure_ascii=False, sort_keys=True), actor, int(time.time())))
        await con.execute("INSERT INTO audit_log(actor_id,action,details,created_at) VALUES(?,?,?,?)", (actor, "add_content", f"{kind}:{key}", int(time.time())))
        await con.commit()
    except Exception: await con.rollback(); raise
    finally: await con.close()

async def list_content(db: Database, kind: str | None = None):
    await initialize_content(db); con = await db.connect()
    try:
        sql = "SELECT kind,content_id,payload_json FROM game_content WHERE kind=? ORDER BY content_id" if kind else "SELECT kind,content_id,payload_json FROM game_content ORDER BY kind,content_id"
        cur = await con.execute(sql, (kind,) if kind else ())
        return [dict(row) for row in await cur.fetchall()]
    finally: await con.close()

async def grant(db: Database, actor: int, action: str, args: list[str]) -> str:
    if action in GRANT_LIMITS:
        if len(args) != 2: raise GameError(f"Usage: /add {action} USER_ID AMOUNT")
        try: target, amount = map(int, args)
        except ValueError as exc: raise GameError("User ID and amount must be whole numbers.") from exc
        if target <= 0 or not 1 <= amount <= GRANT_LIMITS[action]: raise GameError(f"Use a positive user ID and {action} amount from 1 to {GRANT_LIMITS[action]:,}.")
        con = await db.connect()
        try:
            await con.execute("BEGIN IMMEDIATE")
            if not await (await con.execute("SELECT 1 FROM players WHERE telegram_id=?", (target,))).fetchone(): raise GameError("Player profile not found; they must send /start first.")
            if action == "level": await con.execute("UPDATE players SET level=?,xp=0 WHERE telegram_id=?", (amount, target))
            elif action == "energy": await con.execute("UPDATE players SET energy=min(max_energy,energy+?) WHERE telegram_id=?", (amount, target))
            else: await con.execute(f"UPDATE players SET {action}={action}+? WHERE telegram_id=?", (amount, target))
            await con.execute("INSERT INTO audit_log(actor_id,action,target_id,details,created_at) VALUES(?,?,?,?,?)", (actor, "add_"+action, target, str(amount), int(time.time())))
            await con.commit()
        except Exception: await con.rollback(); raise
        finally: await con.close()
        return f"✅ Added {amount:,} {action} to player {target}."
    if action in {"item", "gear", "character", "skill", "pet"}:
        if len(args) != 3: raise GameError(f"Usage: /add {action} USER_ID ID QUANTITY")
        try: target, quantity = int(args[0]), int(args[2])
        except ValueError as exc: raise GameError("User ID and quantity must be whole numbers.") from exc
        if target <= 0 or not 1 <= quantity <= 10000: raise GameError("Use a positive ID and quantity 1–10,000.")
        key = content_id(args[1]); con = await db.connect()
        try:
            await con.execute("BEGIN IMMEDIATE")
            if not await (await con.execute("SELECT 1 FROM players WHERE telegram_id=?", (target,))).fetchone(): raise GameError("Player profile not found; they must send /start first.")
            if action in {"item", "gear"}:
                await con.execute("INSERT INTO owned_items(player_id,item_id,quantity) VALUES(?,?,?) ON CONFLICT(player_id,item_id) DO UPDATE SET quantity=quantity+excluded.quantity", (target, key, quantity))
            elif action == "character":
                await con.execute("INSERT INTO owned_characters(player_id,character_id,shards) VALUES(?,?,?) ON CONFLICT(player_id,character_id) DO UPDATE SET shards=shards+excluded.shards", (target, key, quantity-1))
            elif action == "skill": await con.execute("INSERT OR IGNORE INTO owned_skills(player_id,skill_id) VALUES(?,?)", (target, key))
            else: await con.execute("INSERT INTO owned_pets(player_id,pet_id) VALUES(?,?) ON CONFLICT(player_id,pet_id) DO UPDATE SET level=level+1", (target, key))
            await con.execute("INSERT INTO audit_log(actor_id,action,target_id,details,created_at) VALUES(?,?,?,?,?)", (actor, "add_"+action, target, f"{key} x{quantity}", int(time.time())))
            await con.commit()
        except Exception: await con.rollback(); raise
        finally: await con.close()
        return f"✅ Added {quantity} × {key} ({action}) to player {target}."
    if action == "dragonball":
        if len(args) != 3: raise GameError("Usage: /add dragonball USER_ID STAR QUANTITY")
        try: target, star, quantity = map(int, args)
        except ValueError as exc: raise GameError("Values must be whole numbers.") from exc
        if target <= 0 or not 1 <= star <= 7 or not 1 <= quantity <= 10000: raise GameError("Use a positive ID, star 1–7, and quantity 1–10,000.")
        con = await db.connect()
        try:
            await con.execute("BEGIN IMMEDIATE")
            if not await (await con.execute("SELECT 1 FROM players WHERE telegram_id=?", (target,))).fetchone(): raise GameError("Player profile not found.")
            await con.execute("INSERT INTO dragon_balls(player_id,star,quantity) VALUES(?,?,?) ON CONFLICT(player_id,star) DO UPDATE SET quantity=quantity+excluded.quantity", (target, star, quantity))
            await con.execute("INSERT INTO audit_log(actor_id,action,target_id,details,created_at) VALUES(?,?,?,?,?)", (actor, "add_dragonball", target, f"{star}★ x{quantity}", int(time.time())))
            await con.commit()
        except Exception: await con.rollback(); raise
        finally: await con.close()
        return f"✅ Added {quantity} Dragon Ball(s) ({star}★) to player {target}."
    raise GameError("Unsupported /add action. Use /add to see options.")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; settings: Settings = context.application.bot_data["settings"]
    if not user or user.id not in settings.admin_ids:
        await update.effective_message.reply_text("⛔ Admin only. Add your numeric ID to ADMIN_IDS."); return
    db: Database = context.application.bot_data["db"]
    await initialize_content(db)
    if not context.args:
        rows = [[InlineKeyboardButton(kind.title(), callback_data=f"add:kind:{kind}")] for kind in SCHEMAS]
        text = ("🛠️ <b>Game Manager</b> — add validated content or grant a player.\n"
                "<code>/add coins|gems|xp|energy|level|stat_points USER_ID AMOUNT</code>\n"
                "<code>/add item|gear|character|skill|pet USER_ID ID QUANTITY</code>\n"
                "<code>/add dragonball USER_ID STAR QUANTITY</code>\n<code>/add list [type]</code>\n"
                "Records are data, never executable code.")
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)); return
    action = context.args[0].lower()
    if action == "list":
        kind = context.args[1].lower() if len(context.args) > 1 else None
        if kind and kind not in SCHEMAS: raise GameError("Unknown type. Run /add to view valid types.")
        records = await list_content(db, kind)
        if not records: await update.effective_message.reply_text("No saved admin content yet."); return
        lines = [f"{r['kind']} · {r['content_id']}: {r['payload_json']}" for r in records]
        await update.effective_message.reply_text("Saved content\n" + "\n".join(lines)[:3800]); return
    if action in set(GRANT_LIMITS) | {"item", "gear", "character", "skill", "pet", "dragonball"}:
        await update.effective_message.reply_text(await grant(db, user.id, action, context.args[1:])); return
    if action not in SCHEMAS: raise GameError("Unknown /add type. Use /add to view supported types.")
    key, payload = parse_values(action, " ".join(context.args[1:]))
    await save_content(db, action, key, payload, user.id)
    await update.effective_message.reply_text(f"✅ Saved {action} <b>{key}</b>.", parse_mode="HTML")

async def add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer()
    settings: Settings = context.application.bot_data["settings"]
    if query.from_user.id not in settings.admin_ids: await query.edit_message_text("Admin only."); return
    parts = (query.data or "").split(":")
    if len(parts) != 3 or parts[1] != "kind" or parts[2] not in SCHEMAS: await query.edit_message_text("Unknown content type."); return
    kind = parts[2]
    await query.edit_message_text(f"<b>{kind.title()}</b> fields: <code>ID|{'|'.join(SCHEMAS[kind])}</code>\nReply with /add {kind} followed by ID and values separated by |.", parse_mode="HTML")

def register(application: Application) -> None:
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CallbackQueryHandler(add_callback, pattern=r"^add:kind:"))
