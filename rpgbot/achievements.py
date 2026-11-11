from __future__ import annotations

"""Persistent, one-time player achievements with atomic reward claims."""

import time
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .game import GameError


@dataclass(frozen=True)
class Achievement:
    id: str
    title: str
    description: str
    reward_kind: str
    reward_amount: int


ACHIEVEMENTS = (
    Achievement("level_2", "A New Beginning", "Reach level 2", "coins", 150),
    Achievement("first_victory", "First Victory", "Win one PvE battle", "gems", 5),
    Achievement("seasoned_hunter", "Seasoned Hunter", "Win five PvE battles", "coins", 500),
    Achievement("world_roamer", "World Roamer", "Explore five times", "stat_points", 10),
    Achievement("collector_5", "Growing Collection", "Own five different fighters", "gems", 15),
)
ACHIEVEMENT_BY_ID = {item.id: item for item in ACHIEVEMENTS}


async def initialize(db) -> None:
    con = await db.connect()
    try:
        await con.execute(
            """CREATE TABLE IF NOT EXISTS achievement_claims(
                player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
                achievement_id TEXT NOT NULL,
                claimed_at INTEGER NOT NULL,
                PRIMARY KEY(player_id, achievement_id)
            )"""
        )
        await con.commit()
    finally:
        await con.close()


def _eligible(achievement: Achievement, player, fighter_count: int) -> bool:
    if achievement.id == "level_2":
        return player["level"] >= 2
    if achievement.id == "first_victory":
        return player["pve_wins"] >= 1
    if achievement.id == "seasoned_hunter":
        return player["pve_wins"] >= 5
    if achievement.id == "world_roamer":
        return player["explores"] >= 5
    if achievement.id == "collector_5":
        return fighter_count >= 5
    return False


async def achievement_status(db, player_id: int) -> list[dict]:
    await initialize(db)
    con = await db.connect()
    try:
        player = await (await con.execute(
            "SELECT level, pve_wins, explores FROM players WHERE telegram_id=?", (player_id,)
        )).fetchone()
        if player is None:
            raise GameError("Use /start to create your fighter profile.")
        fighter_count = (await (await con.execute(
            "SELECT COUNT(*) FROM owned_characters WHERE player_id=?", (player_id,)
        )).fetchone())[0]
        claimed_rows = await (await con.execute(
            "SELECT achievement_id FROM achievement_claims WHERE player_id=?", (player_id,)
        )).fetchall()
        claimed = {row["achievement_id"] for row in claimed_rows}
        return [
            {
                "id": achievement.id,
                "title": achievement.title,
                "description": achievement.description,
                "reward_kind": achievement.reward_kind,
                "reward_amount": achievement.reward_amount,
                "eligible": _eligible(achievement, player, fighter_count),
                "claimed": achievement.id in claimed,
            }
            for achievement in ACHIEVEMENTS
        ]
    finally:
        await con.close()


async def claim_achievement(db, player_id: int, achievement_id: str) -> dict:
    achievement = ACHIEVEMENT_BY_ID.get(achievement_id)
    if achievement is None:
        raise GameError("That achievement does not exist.")
    await initialize(db)
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        player = await (await con.execute(
            "SELECT level, pve_wins, explores FROM players WHERE telegram_id=?", (player_id,)
        )).fetchone()
        if player is None:
            raise GameError("Use /start to create your fighter profile.")
        fighter_count = (await (await con.execute(
            "SELECT COUNT(*) FROM owned_characters WHERE player_id=?", (player_id,)
        )).fetchone())[0]
        if not _eligible(achievement, player, fighter_count):
            raise GameError("You have not completed this achievement yet.")
        try:
            await con.execute(
                "INSERT INTO achievement_claims(player_id, achievement_id, claimed_at) VALUES(?,?,?)",
                (player_id, achievement.id, int(time.time())),
            )
        except Exception as exc:
            # SQLite integrity errors indicate a previous claim; other errors propagate.
            if "UNIQUE constraint failed" in str(exc):
                raise GameError("You already claimed this achievement.") from exc
            raise
        if achievement.reward_kind == "coins":
            await con.execute("UPDATE players SET coins=coins+? WHERE telegram_id=?", (achievement.reward_amount, player_id))
        elif achievement.reward_kind == "gems":
            await con.execute("UPDATE players SET gems=gems+? WHERE telegram_id=?", (achievement.reward_amount, player_id))
        elif achievement.reward_kind == "stat_points":
            await con.execute("UPDATE players SET stat_points=stat_points+? WHERE telegram_id=?", (achievement.reward_amount, player_id))
        await con.commit()
        return {"title": achievement.title, "reward_kind": achievement.reward_kind, "reward_amount": achievement.reward_amount}
    except Exception:
        await con.rollback()
        raise
    finally:
        await con.close()


async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        await update.effective_message.reply_text("Unable to identify your Telegram account.")
        return
    db = context.application.bot_data["db"]
    from .game import register_player
    await register_player(db, user.id, user.username, user.full_name or user.first_name or "Fighter")
    status = await achievement_status(db, user.id)
    lines = ["🏅 <b>Achievements</b>"]
    buttons = []
    for item in status:
        if item["claimed"]:
            state = "✅ Claimed"
        elif item["eligible"]:
            state = "🎁 Ready to claim"
            buttons.append([InlineKeyboardButton(f"Claim: {item['title']}", callback_data=f"achievement:claim:{item['id']}")])
        else:
            state = "🔒 In progress"
        lines.append(f"\n<b>{item['title']}</b> — {item['description']}\nReward: {item['reward_amount']} {item['reward_kind']} · {state}")
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )


async def achievement_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db = context.application.bot_data["db"]
    try:
        result = await claim_achievement(db, user.id, (query.data or "").split(":")[-1])
    except GameError as exc:
        await query.edit_message_text(str(exc))
        return
    await query.edit_message_text(
        f"🏅 {result['title']} claimed! Reward: {result['reward_amount']} {result['reward_kind']}.",
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("achievements", achievements_command))
    application.add_handler(CallbackQueryHandler(achievement_callback, pattern=r"^achievement:claim:"))


__all__ = ["ACHIEVEMENTS", "achievement_status", "claim_achievement", "initialize", "register"]
