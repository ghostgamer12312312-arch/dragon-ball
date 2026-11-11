from __future__ import annotations

import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import Settings
from .data_catalog import BANNERS, ITEMS, PETS, resolve_character, resolve_skill
from .game import GameError, GameService


async def banner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = []
    for name, banner in BANNERS.items():
        lines.append(f"{name}: {banner['name']} ({banner['cost']} gems)")
    await update.effective_message.reply_text("🎟️ Banners\n" + "\n".join(lines), reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("1x Spin", callback_data="rpg:banner:1"), InlineKeyboardButton("10x Spin", callback_data="rpg:banner:10")],
        [InlineKeyboardButton("50x Spin", callback_data="rpg:banner:50")],
    ]))


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = []
    for item_id, item in ITEMS.items():
        lines.append(f"{item_id} — {item['name']} ({item['price']} coins)")
    await update.effective_message.reply_text("🛒 Shop\n" + "\n".join(lines))


async def summon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service: GameService = context.application.bot_data["game"]
    user = update.effective_user
    if user is None:
        raise GameError("Could not identify your Telegram account.")
    await service.register(user.id, user.username, user.full_name or "Fighter")
    await update.effective_message.reply_text("✨ Summon menu\nElite key: 1\nBoss key: 1\nUse /summon elite or /summon boss.", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Summon Elite", callback_data="rpg:summon:elite"), InlineKeyboardButton("Summon Boss", callback_data="rpg:summon:boss")],
    ]))


async def skills_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from .data_catalog import SKILLS
    lines = [f"{name} — power {meta['power']}, MP {meta['mp_cost']}, cooldown {meta['cooldown']}" for name, meta in SKILLS.items()]
    await update.effective_message.reply_text("⚡ Skills\n" + "\n".join(lines))


async def pet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"{pet_id} — {pet['name']} ({pet['rarity']}): {pet['bonus']}" for pet_id, pet in PETS.items()]
    await update.effective_message.reply_text("🐾 Pets\n" + "\n".join(lines))


def register_store_and_util_features(application: Application) -> None:
    application.add_handler(CommandHandler("banner", banner_cmd))
    application.add_handler(CommandHandler("gacha", banner_cmd))
    application.add_handler(CommandHandler("pull", banner_cmd))
    application.add_handler(CommandHandler("shop", shop_cmd))
    application.add_handler(CommandHandler("summon", summon_cmd))
    application.add_handler(CommandHandler("skills", skills_cmd))
    application.add_handler(CommandHandler("pets", pet_cmd))
