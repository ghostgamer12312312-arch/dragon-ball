from __future__ import annotations

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .catalog import CHARACTERS, ENEMIES
from .data_catalog import resolve_character
from .game import GameError, GameService

log = logging.getLogger(__name__)


async def characters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service: GameService = context.application.bot_data["game"]
    user = update.effective_user
    if user is None:
        raise GameError("Could not identify your Telegram account.")
    await service.register(user.id, user.username, user.full_name or "Fighter")
    rows = [
        [InlineKeyboardButton(f"{name} · {char['rank']}", callback_data=f"rpg:char:{char['id']}")]
        for name, char in {k: v for k, v in CHARACTERS.items()}.items()
    ]
    if not rows:
        await update.effective_message.reply_text("No characters yet.")
        return
    await update.effective_message.reply_text("Choose a character", reply_markup=InlineKeyboardMarkup(rows[:10]))


async def character_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service: GameService = context.application.bot_data["game"]
    user = update.effective_user
    if user is None:
        raise GameError("Could not identify your Telegram account.")
    if not context.args:
        await update.effective_message.reply_text("Usage: /character <name> or tap from /characters.")
        return
    name = " ".join(context.args)
    char = resolve_character(name)
    if char is None:
        await update.effective_message.reply_text("Unknown character.")
        return
    text = (
        f"{char['name']} · {char['rank']}\n"
        f"Series: {char['series']}\n"
        f"Element: {char['element']}\nTrait: {char['trait']}\nAbility: {char['ability']}\n"
        f"Form: {char['form']}\nStats: HP {char['hp'] if 'hp' in char else 100} / ATK {char['attack'] if 'attack' in char else 20}"
    )
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Equip", callback_data=f"rpg:char:equip:{char['id']}")]]))


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service: GameService = context.application.bot_data["game"]
    user = update.effective_user
    if user is None:
        raise GameError("Could not identify your Telegram account.")
    player = service.profile(user.id)
    text = (
        f"Profile: {player['display_name']}\n"
        f"Level {player['level']} · XP {player['xp']}\n"
        f"Coins {player['coins']} · Gems {player['gems']}\n"
        f"Energy {player['energy']}/{player['max_energy']}\n"
        f"Active fighter: {player['active_character']}"
    )
    await update.effective_message.reply_text(text)


def register_character_features(application: Application) -> None:
    application.add_handler(CommandHandler("characters", characters_cmd))
    application.add_handler(CommandHandler("character", character_detail))
    application.add_handler(CommandHandler("profile", profile_cmd))
