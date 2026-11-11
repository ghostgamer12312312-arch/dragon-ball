from __future__ import annotations

import html
import random
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .game import GameError, register_player


async def ensure_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None:
        raise GameError("Unable to identify your Telegram account.")
    db = context.application.bot_data["db"]
    return await register_player(db, user.id, user.username, user.full_name or user.first_name or "Fighter")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.application.bot_data["db"]
    await ensure_player(update, context)
    con = await db.connect()
    try:
        rows = await (await con.execute(
            "SELECT display_name, level, xp, pve_wins FROM players ORDER BY level DESC, xp DESC, pve_wins DESC LIMIT 10"
        )).fetchall()
    finally:
        await con.close()

    if not rows:
        await update.effective_message.reply_text("No fighters have registered yet.")
        return

    lines = ["🏆 Top fighters:"]
    for index, row in enumerate(rows, 1):
        lines.append(f"{index}. {html.escape(row['display_name'])} — Lv {row['level']} • XP {row['xp']} • PvE {row['pve_wins']}")
    await update.effective_message.reply_text("\n".join(lines))


async def train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await ensure_player(update, context)
    stat = (context.args[0].lower() if context.args else "str").strip()
    valid = {"str": "str_stat", "agi": "agi_stat", "vit": "vit_stat", "int": "int_stat", "luk": "luk_stat"}
    if stat not in valid:
        await update.effective_message.reply_text("Use /train str|agi|vit|int|luk")
        return

    db = context.application.bot_data["db"]
    cost = 25 + player["level"] * 10
    if player["stat_points"] < cost:
        await update.effective_message.reply_text(f"You need {cost} stat points to train {stat.upper()}.")
        return

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute(f"UPDATE players SET stat_points = stat_points - ?, {valid[stat]} = {valid[stat]} + 1 WHERE telegram_id = ?", (cost, player["telegram_id"]))
        await con.commit()
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()

    await update.effective_message.reply_text(f"✅ {stat.upper()} increased by 1. You spent {cost} stat points.")


async def travel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await ensure_player(update, context)
    db = context.application.bot_data["db"]
    region = (context.args[0].lower() if context.args else player["region"]).strip()
    allowed = {"earth": "Earth", "namek": "Namek", "other_world": "Other World", "capsule": "Capsule Corp"}
    if region not in allowed:
        await update.effective_message.reply_text("Travel destinations: earth, namek, other_world, capsule")
        return

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute("UPDATE players SET region = ?, explores = explores + 1 WHERE telegram_id = ?", (region, player["telegram_id"]))
        await con.commit()
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()

    await update.effective_message.reply_text(f"🚀 You traveled to {allowed[region]}. The world becomes a little bigger.")


async def quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await ensure_player(update, context)
    db = context.application.bot_data["db"]
    con = await db.connect()
    try:
        rows = await (await con.execute(
            "SELECT quest_id, progress, claimed FROM player_quests WHERE player_id = ? ORDER BY quest_id",
            (player["telegram_id"],),
        )).fetchall()
    finally:
        await con.close()

    if not rows:
        default = [
            ("daily_train", 0, 0),
            ("fight_3", 0, 0),
            ("travel_1", 0, 0),
        ]
        rows = default

    lines = ["📜 Active quests:"]
    for quest_id, progress, claimed in rows:
        status = "✅ Claimed" if claimed else f"Progress {progress}/3"
        lines.append(f"- {quest_id}: {status}")
    await update.effective_message.reply_text("\n".join(lines))


async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await ensure_player(update, context)
    db = context.application.bot_data["db"]
    boss_names = ["Frieza Force Commander", "Cell Jr.", "Majin Brawler", "Omega Titan"]
    boss = random.choice(boss_names)
    reward = 300 + player["level"] * 25
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute("UPDATE players SET coins = coins + ?, xp = xp + 70 WHERE telegram_id = ?", (reward, player["telegram_id"]))
        await con.commit()
    finally:
        await con.close()

    await update.effective_message.reply_text(f"👑 Raid clear! You defeated {boss} and earned {reward} Zeni and 70 XP.")


async def arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await ensure_player(update, context)
    db = context.application.bot_data["db"]
    opponent = random.choice(["Vegeta Rival", "Cell Clone", "Android 17", "Shadow Saiyan"])
    reward = 180 + player["level"] * 20
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute("UPDATE players SET coins = coins + ?, pvp_wins = pvp_wins + 1 WHERE telegram_id = ?", (reward, player["telegram_id"]))
        await con.commit()
    finally:
        await con.close()

    await update.effective_message.reply_text(f"⚔️ Arena victory! You beat {opponent} and earned {reward} Zeni and a PvP win.")


async def title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await ensure_player(update, context)
    if not context.args:
        await update.effective_message.reply_text("Use /title <your custom title>")
        return

    title_text = " ".join(context.args)[:40]
    db = context.application.bot_data["db"]
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute("UPDATE players SET title = ? WHERE telegram_id = ?", (title_text, player["telegram_id"]))
        await con.commit()
    finally:
        await con.close()

    await update.effective_message.reply_text(f"🏷️ Your title is now: {html.escape(title_text)}")


def register_expansion(application: Application) -> None:
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("train", train))
    application.add_handler(CommandHandler("travel", travel))
    application.add_handler(CommandHandler("quests", quests))
    application.add_handler(CommandHandler("raid", raid))
    application.add_handler(CommandHandler("arena", arena))
    application.add_handler(CommandHandler("title", title))


__all__ = ["register_expansion"]
