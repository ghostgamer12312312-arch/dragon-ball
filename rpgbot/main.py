from __future__ import annotations

import html
import logging
import time

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from .config import Settings
from .database import Database
from .game import GameError, buy_asset, market_page, portfolio, profile, register_player, sell_asset

log=logging.getLogger(__name__)

async def ensure(update:Update,context:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    if not user: raise GameError("Could not identify your Telegram account.")
    db:Database=context.application.bot_data['db']
    return await register_player(db,user.id,user.username,user.full_name or "Fighter")

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    p=await ensure(update,context)
    await update.effective_message.reply_text(f"🐉 Dragon Ball RPG Exchange\nWelcome, {html.escape(p['display_name'])}!\nUse /profile, /market, or /help.")

async def help_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await ensure(update,context)
    await update.effective_message.reply_text("Commands:\n/start — create your fighter\n/profile — view Zeni and level\n/market — Capsule Corp. exchange\n/portfolio — holdings and profit/loss\n\nMarket prices update every five minutes. Trades use fictional in-game Zeni, charge a 1% fee, and can lose value.")

async def profile_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await ensure(update,context)
    p=await profile(context.application.bot_data['db'],update.effective_user.id)
    await update.effective_message.reply_text(f"👤 {html.escape(p['display_name'])}\nLevel {p['level']} · XP {p['xp']}\n💴 Zeni: {p['coins']:,}")

def render_market(rows,page,pages,coins):
    lines=["⚔️ <b>CAPSULE CORP. EXCHANGE</b>",f"📊 {len(rows)} assets on this page · prices update every 5 min",f"💴 Your Zeni: <b>{coins:,}</b> · Fee: 1%",""]
    buttons=[]
    for r in rows:
        arrow='📈' if r['change_pct']>=0 else '📉'
        lines.append(f"{r['emoji']} <b>{r['name']}</b> [{r['asset_id'].upper()}]\n💎 {r['price']:,} Zeni {arrow} {r['change_pct']:+.1f}% · 📦 {r['stock']:,} left")
        buttons.append([InlineKeyboardButton(f"{r['emoji']} {r['asset_id'].upper()} · {r['price']:,}",callback_data=f"market:asset:{r['asset_id']}")])
    lines.append(f"\n📄 Page {page+1}/{pages} · Tap an asset to trade. Quotes can rise or fall.")
    nav=[]
    if page:nav.append(InlineKeyboardButton("⬅️ Previous",callback_data=f"market:page:{page-1}"))
    if page+1<pages:nav.append(InlineKeyboardButton("Next ➡️",callback_data=f"market:page:{page+1}"))
    if nav:buttons.append(nav)
    buttons.append([InlineKeyboardButton("💼 Portfolio",callback_data="market:portfolio")])
    return "\n".join(lines),InlineKeyboardMarkup(buttons)

async def market_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await ensure(update,context)
    db=context.application.bot_data['db']; rows,page,pages=await market_page(db)
    p=await profile(db,update.effective_user.id)
    text,markup=render_market(rows,page,pages,p['coins'])
    await update.effective_message.reply_text(text,parse_mode='HTML',reply_markup=markup)

async def portfolio_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await ensure(update,context)
    await update.effective_message.reply_text(await portfolio(context.application.bot_data['db'],update.effective_user.id),parse_mode='HTML')

async def callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    await ensure(update,context)
    db=context.application.bot_data['db']; parts=(query.data or '').split(':'); uid=query.from_user.id
    try:
        if parts[1]=='page':
            rows,page,pages=await market_page(db,int(parts[2])); p=await profile(db,uid)
            text,markup=render_market(rows,page,pages,p['coins'])
            await query.edit_message_text(text,parse_mode='HTML',reply_markup=markup)
        elif parts[1]=='portfolio':
            await query.edit_message_text(await portfolio(db,uid),parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Exchange",callback_data="market:page:0")]]))
        elif parts[1]=='asset':
            asset_id=parts[2]; rows,_,_=await market_page(db,0)
            # Resolve all assets, not only the first page.
            con=await db.connect()
            try:
                cur=await con.execute("SELECT * FROM market_assets WHERE asset_id=?",(asset_id,)); a=await cur.fetchone()
                cur=await con.execute("SELECT quantity FROM market_positions WHERE player_id=? AND asset_id=?",(uid,asset_id)); pos=await cur.fetchone()
            finally: await con.close()
            if not a: raise GameError("Unknown asset.")
            owned=pos['quantity'] if pos else 0; movement='📈' if a['change_pct']>=0 else '📉'
            text=f"{a['emoji']} <b>{a['name']}</b>\n{a['description']}\n\n💎 {a['price']:,} Zeni {movement} {a['change_pct']:+.1f}%\n📦 Stock: {a['stock']:,} · Your holdings: {owned}\n1% trade fee. Profit is not guaranteed."
            buttons=[]
            for qty in (1,5,10):
                if qty<=a['stock']:buttons.append(InlineKeyboardButton(f"Buy ×{qty}",callback_data=f"market:buy:{asset_id}:{qty}"))
            if owned:
                for qty in sorted(set((1,min(5,owned),min(10,owned),owned))):
                    if qty:buttons.append(InlineKeyboardButton(f"Sell ×{qty}",callback_data=f"market:sell:{asset_id}:{qty}"))
            keyboard=[buttons[i:i+2] for i in range(0,len(buttons),2)]+[[InlineKeyboardButton("⬅️ Exchange",callback_data="market:page:0")]]
            await query.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(keyboard))
        elif parts[1] in {'buy','sell'}:
            side,asset_id,qty=parts[1],parts[2],int(parts[3])
            if side=='buy':
                r=await buy_asset(db,uid,asset_id,qty)
                text=f"✅ Bought {r['quantity']} × {r['name']} at {r['unit_price']:,} each. Total {r['total']:,} Zeni including {r['fee']:,} fee. Remaining {r['coins_left']:,}. Future value can rise or fall."
            else:
                r=await sell_asset(db,uid,asset_id,qty)
                text=f"✅ Sold {r['quantity']} × {r['name']} at {r['unit_price']:,} each. Proceeds {r['proceeds']:,} after {r['fee']:,} fee. Realized P/L: {r['realized']:+,} Zeni."
            await query.edit_message_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Exchange",callback_data="market:page:0"),InlineKeyboardButton("Portfolio",callback_data="market:portfolio")]]))
    except (GameError,ValueError) as exc:
        await query.edit_message_text(str(exc))
    except Exception as exc:
        log.exception("Callback failed: %s",type(exc).__name__)
        await query.edit_message_text("Action failed safely. Refresh the exchange and try again.")

async def post_init(app:Application):
    await app.bot.set_my_commands([BotCommand('start','Create your fighter'),BotCommand('help','Show commands'),BotCommand('profile','View profile'),BotCommand('market','Open Capsule Corp exchange'),BotCommand('portfolio','View your holdings')])

async def on_error(update,context):
    log.error("Unhandled Telegram error type=%s",type(context.error).__name__ if context.error else 'unknown')

def build_application(settings:Settings,db:Database):
    app=ApplicationBuilder().token(settings.bot_token).post_init(post_init).build()
    app.bot_data['db']=db
    for name,handler in {'start':start,'help':help_cmd,'profile':profile_cmd,'market':market_cmd,'portfolio':portfolio_cmd}.items():app.add_handler(CommandHandler(name,handler))
    app.add_handler(CallbackQueryHandler(callback,pattern=r'^market:'))
    app.add_error_handler(on_error)
    return app
