from __future__ import annotations

import asyncio
import html
import json
import logging
import time
from datetime import UTC, datetime

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from .config import Settings
from .database import Database
from .data_catalog import ALL_CHARACTERS, BANNERS, CHARACTERS, DUNGEONS, GEAR, ITEMS, PETS, REGIONS, SERIES, SKILLS
from .game import GameError, battle_action, buy_asset, daily_reward, market_page, portfolio, profile, register_player, sell_asset, set_character, start_battle

log=logging.getLogger(__name__)

async def ensure(update,context):
    u=update.effective_user
    if not u: raise GameError('Could not identify your Telegram account.')
    return await register_player(context.application.bot_data['db'],u.id,u.username,u.full_name or 'Fighter')

async def reply(update,text,**kwargs):
    if update.effective_message: await update.effective_message.reply_text(text,**kwargs)

async def start(update,context):
    p=await ensure(update,context); await reply(update,f"🐉 Dragon Ball RPG\nWelcome {html.escape(p['display_name'])}! Use /help to see commands.")

COMMAND_HELP="""PLAYER
/start /help /profile /team /characters /character /equipchar /levelup
/skills /learn /skill_equip /inv /inventory /gear /equip /unequip /use
/forge /craft /enhance /banner /gacha /pull /summon /shop /dailybuy /buy /sell /wish
/hunt /explore /dungeon /duel /travel /series /npc /daily /quests /top /titles /settings
/clan /clan_create /clan_donate /clan_leave /clanraid /clanraid_start
/market /portfolio /market_sell /market_buy /market_cancel
/pets /pet /pet_equip /pet_feed /pet_summon
ADMIN (ADMIN_IDS only)
/crown /upload /admin /give /setlevel /broadcast
Inline buttons are used for gameplay menus. Battles are manual turn-by-turn; foes never auto-battle."""

async def help_cmd(update,context): await ensure(update,context); await reply(update,COMMAND_HELP)

async def profile_cmd(update,context):
    p=await ensure(update,context)
    bar='█'*min(10,int(p['xp']%100/10))+'░'*(10-min(10,int(p['xp']%100/10)))
    await reply(update,f"👤 {html.escape(p['display_name'])}\nID {p['telegram_id']} · Region {p['region']}\nLevel {p['level']} · XP {p['xp']} [{bar}]\n💴 {p['coins']:,} Zeni · 💎 {p['gems']:,} gems\n❤️ Energy {p['energy']}/{p['max_energy']}\nSTR {p['str_stat']} · AGI {p['agi_stat']} · INT {p['int_stat']} · VIT {p['vit_stat']} · LUK {p['luk_stat']} · points {p['stat_points']}\nPvE wins {p['pve_wins']} · PvP wins {p['pvp_wins']} · Explores {p['explores']}\nTitle: {p['title'] or 'None'}")

async def market_cmd(update,context):
    p=await ensure(update,context); rows,page,pages=await market_page(context.application.bot_data['db'])
    text,markup=render_market(rows,page,pages,p['coins']); await reply(update,text,parse_mode='HTML',reply_markup=markup)

def render_market(rows,page,pages,coins):
    lines=[f"⚔️ <b>CAPSULE CORP. EXCHANGE</b>\n💴 Zeni {coins:,} · quotes every 5 minutes · 1% fee\n"]
    buttons=[]
    for r in rows:
        arrow='📈' if r['change_pct']>=0 else '📉'; lines.append(f"{r['emoji']} <b>{r['name']} [{r['asset_id'].upper()}]</b>\n💎 {r['price']:,} Zeni {arrow} {r['change_pct']:+.1f}% · 📦 {r['stock']:,} left")
        buttons.append([InlineKeyboardButton(f"{r['emoji']} {r['asset_id'].upper()} · {r['price']:,}",callback_data=f"market:asset:{r['asset_id']}")])
    lines.append(f"\nPage {page+1}/{pages} · Tap an asset. Values can rise or fall.")
    nav=[]
    if page:nav.append(InlineKeyboardButton('⬅️',callback_data=f'market:page:{page-1}'))
    if page+1<pages:nav.append(InlineKeyboardButton('➡️',callback_data=f'market:page:{page+1}'))
    if nav:buttons.append(nav)
    buttons.append([InlineKeyboardButton('💼 Portfolio',callback_data='market:portfolio')])
    return '\n'.join(lines),InlineKeyboardMarkup(buttons)

async def portfolio_cmd(update,context):
    await ensure(update,context); await reply(update,await portfolio(context.application.bot_data['db'],update.effective_user.id),parse_mode='HTML')

async def battle_command(update,context,kind):
    await ensure(update,context); b=await start_battle(context.application.bot_data['db'],update.effective_user.id,kind)
    await reply(update,battle_text(b),parse_mode='HTML',reply_markup=battle_markup(b['id']))

def battle_markup(bid):
    return InlineKeyboardMarkup([[InlineKeyboardButton('⚔️ Attack',callback_data=f'battle:{bid}:attack'),InlineKeyboardButton('🌀 Dodge',callback_data=f'battle:{bid}:dodge')],[InlineKeyboardButton('💥 Skill 1',callback_data=f'battle:{bid}:skill1'),InlineKeyboardButton('✨ Skill 2',callback_data=f'battle:{bid}:skill2')],[InlineKeyboardButton('🔥 Transform',callback_data=f'battle:{bid}:transform'),InlineKeyboardButton('🔄 Switch',callback_data=f'battle:{bid}:switch')],[InlineKeyboardButton('🏃 Flee',callback_data=f'battle:{bid}:flee')]])

def battle_text(b):
    def bar(v,m):
        f=max(0,min(10,int(10*v/max(1,m))));return '█'*f+'░'*(10-f)
    return f"⚔️ <b>{html.escape(b['kind'].title())}: {html.escape(b['enemy'])}</b> · Turn {b['turn']+1}\n❤️ You {bar(b['player_hp'],b['player_max_hp'])} {b['player_hp']}/{b['player_max_hp']}\n🔵 MP {b['mp']}/100 · 🌟 ULT {b['ult']}%\n👹 Enemy {bar(b['enemy_hp'],b['enemy_max_hp'])} {b['enemy_hp']}/{b['enemy_max_hp']}\nChoose your move. The enemy only acts after your choice."

async def hunt(update,context): await battle_command(update,context,'hunt')
async def dungeon(update,context): await battle_command(update,context,'dungeon')

async def characters(update,context):
    await ensure(update,context)
    buttons=[[InlineKeyboardButton(f"{data['icon']} {name}",callback_data=f"series:{idx}")] for idx,(name,data) in enumerate(SERIES.items())]
    await reply(update,'Choose an anime series:',reply_markup=InlineKeyboardMarkup(buttons))

async def character(update,context):
    await ensure(update,context)
    if context.args:
        q=' '.join(context.args).lower(); c=next((x for x in ALL_CHARACTERS if x['id']==q or x['name'].lower()==q),None)
        if c: await show_character(update,c); return
    buttons=[[InlineKeyboardButton(f"{c['name']} [{c['rank']}]",