from __future__ import annotations

import logging
from typing import Any

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .catalog import CHARACTERS
from .config import Settings
from .database import Database
from .game import GameError, GameService

log = logging.getLogger(__name__)


def admin_dashboard(db: Database) -> str:
    with db.reader() as con:
        players = con.execute("SELECT COUNT(*) AS total FROM players").fetchone()["total"]
        clans = con.execute("SELECT COUNT(*) AS total FROM clans").fetchone()["total"]
        return f"Admin overview\nPlayers: {players}\nClans: {clans}"


def grant_player(db: Database, telegram_id: int, *, coins: int = 0, gems: int = 0) -> str:
    with db.transaction() as con:
        row = con.execute("SELECT telegram_id FROM players WHERE telegram_id=?", (telegram_id,)).fetchone()
        if row is None:
            raise GameError("Player has not started the bot yet. Use /start first.")
        con.execute("UPDATE players SET coins=coins+?, gems=gems+? WHERE telegram_id=?", (coins, gems, telegram_id))
    return f"Granted {coins} coins and {gems} gems to {telegram_id}."


def set_level(db: Database, telegram_id: int, level: int) -> str:
    if level < 1:
        raise GameError("Level must be at least 1.")
    with db.transaction() as con:
        row = con.execute("SELECT telegram_id FROM players WHERE telegram_id=?", (telegram_id,)).fetchone()
        if row is None:
            raise GameError("Player has not started the bot yet. Use /start first.")
        con.execute("UPDATE players SET level=? WHERE telegram_id=?", (level, telegram_id))
    return f"Set player {telegram_id} to level {level}."


def register_admin_tools(application: Application) -> None:
    async def crown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings: Settings = context.application.bot_data["settings"]
        if update.effective_user is None or update.effective_user.id not in settings.admin_ids:
            await update.effective_message.reply_text("Admin only.")
            return
        categories = ["heroes", "npcs", "boss", "summons", "map"]
        active = context.args[0].lower() if context.args else "heroes"
        items = [
            ("heroes", list(CHARACTERS.keys())[:10]),
            ("npcs", ["saibaman", "android_prototype"]),
            ("boss", ["world_eater"]),
            ("summons", ["elite", "boss"]),
            ("map", ["earth", "namek", "other_world"]),
        ]
        selected = dict(items).get(active, items[0][1])
        db = context.application.bot_data["game"].db
        rows = []
        for name in selected:
            with db.reader() as con:
                found = bool(con.execute("SELECT 1 FROM custom_art WHERE entity_key=?", (name.lower(),)).fetchone())
            rows.append((name, found))
        have = sum(1 for _, ok in rows if ok)
        prefix = "👑 Crown"
        body = "\n".join(("✅ " if ok else "❌ ") + name.title() for name, ok in rows)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(cat.upper(), callback_data=f"rpg:admin:{cat}") for cat in categories]])
        await update.effective_message.reply_text(f"{prefix} · {active.title()} — {have}/{len(rows)} have art\n{body}\nUpload: reply to a photo with /upload NAME", reply_markup=markup)

    async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings: Settings = context.application.bot_data["settings"]
        user = update.effective_user
        msg = update.effective_message
        if user is None or user.id not in settings.admin_ids:
            await msg.reply_text("Admin only.")
            return
        if not msg or not msg.reply_to_message or not msg.reply_to_message.photo or not context.args:
            await msg.reply_text("Reply to a photo with /upload <entity_name>.")
            return
        key = " ".join(context.args).strip().lower()
        file_id = msg.reply_to_message.photo[-1].file_id
        db = context.application.bot_data["game"].db
        with db.transaction() as con:
            con.execute("INSERT INTO custom_art(entity_key, file_id, uploaded_by, updated_at) VALUES(?,?,?,?) ON CONFLICT(entity_key) DO UPDATE SET file_id=excluded.file_id, uploaded_by=excluded.uploaded_by, updated_at=excluded.updated_at", (key, file_id, user.id, 0))
        await msg.reply_text(f"✅ Art saved for {key}.")

    async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings: Settings = context.application.bot_data["settings"]
        if update.effective_user is None or update.effective_user.id not in settings.admin_ids:
            await update.effective_message.reply_text("Admin only.")
            return
        service: GameService = context.application.bot_data["game"]
        db = service.db
        await update.effective_message.reply_text(admin_dashboard(db))

    async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings: Settings = context.application.bot_data["settings"]
        if update.effective_user is None or update.effective_user.id not in settings.admin_ids:
            await update.effective_message.reply_text("Admin only.")
            return
        if len(context.args) < 3:
            await update.effective_message.reply_text("Usage: /give <telegram_id> <coins> <gems>")
            return
        try:
            user_id = int(context.args[0])
            coins = int(context.args[1])
            gems = int(context.args[2])
        except ValueError:
            await update.effective_message.reply_text("IDs and values must be numbers.")
            return
        db = context.application.bot_data["game"].db
        await update.effective_message.reply_text(grant_player(db, user_id, coins=coins, gems=gems))

    async def setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings: Settings = context.application.bot_data["settings"]
        if update.effective_user is None or update.effective_user.id not in settings.admin_ids:
            await update.effective_message.reply_text("Admin only.")
            return
        if len(context.args) != 2:
            await update.effective_message.reply_text("Usage: /setlevel <telegram_id> <level>")
            return
        try:
            user_id = int(context.args[0])
            level = int(context.args[1])
        except ValueError:
            await update.effective_message.reply_text("Use numeric values.")
            return
        db = context.application.bot_data["game"].db
        await update.effective_message.reply_text(set_level(db, user_id, level))

    async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings: Settings = context.application.bot_data["settings"]
        if update.effective_user is None or update.effective_user.id not in settings.admin_ids:
            await update.effective_message.reply_text("Admin only.")
            return
        if not context.args:
            await update.effective_message.reply_text("Usage: /broadcast <message>")
            return
        app: Application = context.application
        msg = " ".join(context.args)
        log.info("Broadcast: %s", msg)
        await app.bot.send_message(chat_id=settings.admin_ids.pop() if settings.admin_ids else -1000000000, text=f"📢 {msg}")

    application.add_handler(CommandHandler("crown", crown))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CommandHandler("setlevel", setlevel))
    application.add_handler(CommandHandler("broadcast", broadcast))
