from __future__ import annotations

import json
import logging
import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .config import Settings
from .database import Database
from .game import GameError

log = logging.getLogger(__name__)

# Content types are intentionally whitelisted. Admin input is data, never Python,
# SQL, or executable code. Every record is versioned/persisted in SQLite.
SCHEMAS: dict[str, tuple[str, ...]] = {
    "item": ("name", "description", "price", "effect", "amount"),
    "character": ("name", "series", "rank", "rarity", "element", "trait", "ability", "hp", "attack"),
    "skill": ("name", "power", "mp_cost", "cooldown", "kind"),
    "enemy": ("name", "hp", "attack", "coins", "xp"),
    "pet": ("name", "rarity", "bonus", "price"),
    "region": ("name", "weather", "level", "description"),
    "gear": ("name", "slot", "attack", "defense", "rarity"),
    "recipe": ("name", "output", "materials", "quantity"),
    "banner": ("name", "price", "featured"),
    "title": ("name", "description"),
}

NUMERIC_FIELDS = {"price", "amount", "rarity", "hp", "attack", "power", "mp_cost", "cooldown", "coins", "xp", "level", "defense", "quantity"}


def init_content_table(db: Database) -> None:
    """Synchronous helper is not used by Telegram runtime; see initialize_content."""
    raise RuntimeError("Use await initialize_content(db)")


async def initialize_content(db: Database) -> None:
    con = await db.connect()
    try:
        await con.execute("""CREATE TABLE IF NOT EXISTS game_content(
            kind TEXT NOT NULL, content_id TEXT NOT NULL, payload_json TEXT NOT NULL,
            created_by INTEGER NOT NULL, created_at INTEGER NOT NULL,
            PRIMARY KEY(kind,content_id))""")
        await con.commit()
    finally:
        await con.close()


def _content_id(value: str) -> str:
    import re
    key = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")
    if not key or len(key) > 48:
        raise GameError("Content ID must contain 1–48 letters, numbers, or underscores.")
    return key


def parse_values(kind: str, raw: str) -> tuple[str, dict[str, Any]]:
    schema = SCHEMAS.get(kind)
    if schema is None:
        raise GameError("Unknown content type. Choose: " + ", ".join(SCHEMAS))
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != len(schema) + 1:
        raise GameError(f"For {kind}, provide ID plus {', '.join(schema)} separated by |.")
    content_id = _content_id(parts[0])
    payload: dict[str, Any] = {}
    for field, value in zip(schema, parts[1:]):
        if not value:
            raise GameError(f"{field} cannot be empty.")
        if field in NUMERIC_FIELDS:
            try:
                payload[field] = int(value)
            except ValueError as exc:
                raise GameError(f"{field} must be a whole number.") from exc
        else:
            payload[field] = value[:240]
    for field in ("price", "amount", "hp", "attack", "power", "mp_cost", "cooldown", "coins", "xp", "level", "defense", "quantity"):
        if field in payload and payload[field] < 0:
            raise GameError(f"{field} cannot be negative.")
    if "price" in payload and payload["price"] == 0:
        raise GameError("price must be greater than zero.")
    if "hp" in payload and payload["hp"] < 1:
        raise GameError("hp must be at least 1.")
    if "rank" in payload and payload["rank"].upper() not in {"Z", "S", "A", "B", "E"}:
        raise GameError("rank must be Z, S, A, B, or E.")
    if "rarity" in payload and isinstance(payload["rarity"], int) and not 1 <= payload["rarity"] <= 5:
        raise GameError("rarity must be from 1 to 5.")
    return content_id, payload


async def save_content(db: Database, kind: str, content_id: str, payload: dict[str, Any], actor: int) -> None:
    if kind not in SCHEMAS:
        raise GameError("Unsupported content type.")
    await initialize_content(db)
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute("INSERT INTO game_content(kind,content_id,payload_json,created_by,created_at) VALUES(?,?,?,?,?) "
                          "ON CONFLICT(kind,content_id) DO UPDATE SET payload_json=excluded.payload_json,created_by=excluded.created_by,created_at=excluded.created_at",
                          (kind, content_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), actor, int(time.time())))
        await con.commit()
    except Exception:
        await con.rollback()
        raise
    finally:
        await con.close()


async def list_content(db: Database, kind: str | None = None):
    await initialize_content(db)
    con = await db.connect()
    try:
        if kind:
            cur = await con.execute("SELECT content_id,payload_json FROM game_content WHERE kind=? ORDER BY content_id", (kind,))
        else:
            cur = await con.execute("SELECT kind,content_id,payload_json FROM game_content ORDER BY kind,content_id")
        return [dict(row) for row in await cur.fetchall()]
    finally:
        await con.close()


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    settings: Settings = context.application.bot_data["settings"]
    if user is None or user.id not in settings.admin_ids:
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Admin only. Configure your Telegram ID in ADMIN_IDS.")
        return
    if not context.args:
        rows = [[InlineKeyboardButton(kind.title(), callback_data=f"add:kind:{kind}")] for kind in SCHEMAS]
        text = ("🛠️ <b>Game Content Manager</b>\nSelect content to create/update.\n\n"
                "Also supports grants: <code>/add coins USER_ID AMOUNT</code>, "
                "<code>/add gems USER_ID AMOUNT</code>, <code>/add item USER_ID ITEM_ID QUANTITY</code>.\n"
                "Content records are validated data; this command never executes code.")
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return
    action = context.args[0].lower()
    if action in {"coins", "gems", "item", "character"} and len(context.args) >= 2 and context.args[1].isdigit():
        await _grant(update, context, action)
        return
    if action == "list":
        kind = context.args[1].lower() if len(context.args) > 1 else None
        if kind and kind not in SCHEMAS:
            raise GameError("Unknown content type.")
        records = await list_content(context.application.bot_data["db"], kind)
        if not records:
            await update.effective_message.reply_text("No admin-added content yet.")
            return
        lines = [f"{r.get('kind',kind)} · {r['content_id']}: {r['payload_json']}" for r in records]
        await update.effective_message.reply_text("🗂️ Game content\n" + "\n".join(lines)[:3900])
        return
    if action not in SCHEMAS:
        raise GameError("Usage: /add [" + "|".join(SCHEMAS) + "] ID|field1|field2|... or /add coins USER_ID AMOUNT")
    raw = " ".join(context.args[1:])
    content_id, payload = parse_values(action, raw)
    await save_content(context.application.bot_data["db"], action, content_id, payload, user.id)
    await update.effective_message.reply_text(f"✅ Saved {action} <b>{content_id}</b>. Use /add list {action} to view records.", parse_mode="HTML")


async def _grant(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    args = context.args
    db: Database = context.application.bot_data["db"]
    if action == "item":
        if len(args) != 4:
            raise GameError("Usage: /add item USER_ID ITEM_ID QUANTITY")
        try: target, quantity = int(args[1]), int(args[3])
        except ValueError as exc: raise GameError("User ID and quantity must be whole numbers.") from exc
        item_id = _content_id(args[2])
        if target <= 0 or not 1 <= quantity <= 10000: raise GameError("Use a positive user ID and quantity 1–10000.")
        con=await db.connect()
        try:
            await con.execute("BEGIN IMMEDIATE")
            cur=await con.execute("SELECT 1 FROM players WHERE telegram_id=?",(target,))
            if not await cur.fetchone(): raise GameError("Player profile not found; they must send /start first.")
            await con.execute("INSERT INTO owned_items(player_id,item_id,quantity) VALUES(?,?,?) ON CONFLICT(player_id,item_id) DO UPDATE SET quantity=quantity+excluded.quantity",(target,item_id,quantity))
            await con.execute("INSERT INTO audit_log(actor_id,action,target_id,details,created_at) VALUES(?,?,?,?,?)",(update.effective_user.id,"grant_item",target,f"{item_id} x{quantity}",int(time.time())))
            await con.commit()
        except Exception: await con.rollback(); raise
        finally: await con.close()
        await update.effective_message.reply_text(f"✅ Granted {quantity} × {item_id} to {target}.")
        return
    if len(args) != 3:
        raise GameError(f"Usage: /add {action} USER_ID AMOUNT")
    try: target, amount = int(args[1]), int(args[2])
    except ValueError as exc: raise GameError("User ID and amount must be whole numbers.") from exc
    if target <= 0 or not 1 <= amount <= 1_000_000:
        raise GameError("Use a positive user ID and amount from 1 to 1,000,000.")
    if action == "character":
        char_id=_content_id(args[2])
        con=await db.connect()
        try:
            await con.execute("BEGIN IMMEDIATE")
            cur=await con.execute("SELECT 1 FROM players WHERE telegram_id=?",(target,))
            if not await cur.fetchone(): raise GameError("Player profile not found; they must send /start first.")
            await con.execute("INSERT OR IGNORE INTO owned_characters(player_id,character_id) VALUES(?,?)",(target,char_id))
            await con.execute("INSERT INTO audit_log(actor_id,action,target_id,details,created_at) VALUES(?,?,?,?,?)",(update.effective_user.id,"grant_character",target,char_id,int(time.time())))
            await con.commit()
        except Exception: await con.rollback(); raise
        finally: await con.close()
        await update.effective_message.reply_text(f"✅ Added character {char_id} to player {target}.")
        return
    column = "coins" if action == "coins" else "gems"
    con=await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        cur=await con.execute("SELECT 1 FROM players WHERE telegram_id=?",(target,))
        if not await cur.fetchone(): raise GameError("Player profile not found; they must send /start first.")
        await con.execute(f"UPDATE players SET {column}={column}+? WHERE telegram_id=?",(amount,target))
        await con.execute("INSERT INTO audit_log(actor_id,action,target_id,details,created_at) VALUES(?,?,?,?,?)",(update.effective_user.id,f"grant_{column}",target,str(amount),int(time.time())))
        await con.commit()
    except Exception: await con.rollback(); raise
    finally: await con.close()
    await update.effective_message.reply_text(f"✅ Granted {amount:,} {column} to player {target}.")


async def add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    settings: Settings = context.application.bot_data["settings"]
    if query.from_user.id not in settings.admin_ids:
        await query.edit_message_text("Admin only.")
        return
    kind = (query.data or "").split(":")[-1]
    if kind not in SCHEMAS:
        await query.edit_message_text("Unknown content type.")
        return
    fields = "|".join(SCHEMAS[kind])
    await query.edit_message_text(
        f"Add or update a {kind}. Send this command with pipe-separated fields:\n\n"
        f"<code>/add {kind} ID|{fields}</code>\n\n"
        "Example: <code>/add item senzu|Senzu Bean|Restores energy|40|energy|40</code>",
        parse_mode="HTML",
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CallbackQueryHandler(add_callback, pattern=r"^add:kind:"))
