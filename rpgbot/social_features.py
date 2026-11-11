from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("🏆 Top players: level, coins, PvP wins, and clan rank")


async def titles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("🏅 Player titles: Guardian, Rogue, Elite, Hero, Godslayer")


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("⚙️ Settings: notifications, sound, avatar, auto-join, private raids")


def register_social_features(application: Application) -> None:
    application.add_handler(CommandHandler("top", top_cmd))
    application.add_handler(CommandHandler("titles", titles_cmd))
    application.add_handler(CommandHandler("settings", settings_cmd))
