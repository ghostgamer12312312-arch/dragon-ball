from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .data_catalog import DUNGEONS, REGIONS


async def travel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [[InlineKeyboardButton(f"{name} ({meta['weather']})", callback_data=f"rpg:travel:{region}")] for region, meta in REGIONS.items()]
    await update.effective_message.reply_text("🌍 Travel destinations", reply_markup=InlineKeyboardMarkup(buttons))


async def dungeon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [[InlineKeyboardButton(f"{name} ({difficulty})", callback_data=f"rpg:dungeon:{dungeon_id}")] for dungeon_id, (name, difficulty) in [(d, (meta['name'], meta['difficulty'])) for d, meta in DUNGEONS.items()]]
    await update.effective_message.reply_text("🗺️ Dungeons", reply_markup=InlineKeyboardMarkup(buttons))


async def series_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from .data_catalog import SERIES
    buttons = [[InlineKeyboardButton(f"{series} {meta['icon']}", callback_data=f"rpg:series:{series}")] for series, meta in SERIES.items()]
    await update.effective_message.reply_text("📚 Anime series", reply_markup=InlineKeyboardMarkup(buttons))


async def npc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("NPCs available: Elder, Merchant, Arena Guide, Clan Captain")


def register_world_features(application: Application) -> None:
    application.add_handler(CommandHandler("travel", travel_cmd))
    application.add_handler(CommandHandler("dungeon", dungeon_cmd))
    application.add_handler(CommandHandler("series", series_cmd))
    application.add_handler(CommandHandler("npc", npc_cmd))
