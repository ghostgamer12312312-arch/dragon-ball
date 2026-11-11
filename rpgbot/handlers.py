from __future__ import annotations

import asyncio
import logging
from functools import wraps

from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from .config import Settings
from .game import GameError, GameService

log=logging.getLogger(__name__)


def player(update:Update):
    user=update.effective_user
    if user is None: raise GameError("Could not identify your Telegram account.")
    return user.id,user.username,user.full_name or "Fighter"

async def reply(update:Update,text:str):
    if update.effective_message: await update.effective_message.reply_text(text)

def command(name):
    def deco(fn):
        @wraps(fn)
        async def wrapper(update:Update,context:ContextTypes.DEFAULT_TYPE):
            try: await fn(update,context)
            except GameError as exc: await reply(update,str(exc))
            except Exception as exc:
                log.error("Command %s failed: %s",name,type(exc).__name__)
                await reply(update,"A temporary error occurred. Please try again later.")
        return wrapper
    return deco

async def call(update,service,fn,*args):
    try: return await asyncio.to_thread(fn,*args)
    except GameError as exc:
        await reply(update,str(exc)); return None

@command("start")
async def start(update,context):
    s=context.application.bot_data["game"]; pid,username,name=player(update)
    p,created=await asyncio.to_thread(s.register,pid,username,name)
    await reply(update,f"🐉 Dragon Realm RPG\nWelcome, {p['display_name']}! {'Your Goku starter fighter is ready.' if created else 'Welcome back.'}\n\nUse /help to begin.")

@command("help")
async def help_cmd(update,context):
    await reply(update,"DRAGON REALM RPG — COMMANDS\n/start · /profile · /explore · /train · /rest · /daily\n/quests · /claim <quest_id> · /summon · /collection · /select <fighter_id>\n/shop · /buy <item_id> [quantity] · /inventory · /use <item_id>\n/leaderboard · /clan · /clan_create <name> · /clan_join <id> · /clan_leave · /clan_disband\n/raid · /raid_attack\nAdmins configured in ADMIN_IDS: /admin_stats · /ban <id> · /unban <id>\nStart with /start. Explore and train cost energy; daily rewards can be claimed once per UTC day.")

@command("profile")
async def profile(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); p=await call(update,s,s.profile,pid)
    if p: await reply(update,f"👤 {p['display_name']}\nLevel {p['level']} · XP {p['xp']}/{p['level']*100}\nCoins {p['coins']} · Gems {p['gems']}\nEnergy {p['energy']}/{p['max_energy']}\nFighter: {p['fighter']['name']} ({p['fighter']['rarity']})\nCollection: {p['collection_size']} fighters · Daily streak: {p['daily_streak']}")

@command("explore")
async def explore(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.explore,pid)
    if r: await reply(update,f"{'✅ Victory' if r['won'] else '❌ Defeat'} vs {r['enemy']}\nHP remaining: {r['hp_left']}\nRewards: {r['coins']} coins, {r['xp']} XP\nEnergy: {r['energy']}/{r['max_energy']}"+(f"\nLevel up! Level {r['level']}." if r['levels'] else ""))

@command("train")
async def train(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.train,pid)
    if r: await reply(update,f"Training: +{r['xp']} XP. Level {r['level']} · {r['xp']}/{r['level']*100} XP · Energy {r['energy']}/{r['max_energy']}.")

@command("rest")
async def rest(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.rest,pid)
    if r: await reply(update,f"Rested. Energy {r['energy']}/{r['max_energy']}; {r['coins']} coins remain.")

@command("daily")
async def daily(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.daily,pid)
    if r: await reply(update,f"📅 Daily reward: +{r['coins']} coins, energy {r['energy']}/{r['max_energy']}. Streak: {r['streak']} day(s).")

@command("quests")
async def quests(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); rows=await call(update,s,s.quests,pid)
    if rows is not None: await reply(update,"📋 DAILY QUESTS (UTC)\n"+"\n".join(f"{'✅' if q['claimed'] else '🎁' if q['progress']>=q['goal'] else '▫️'} {q['id']}: {q['name']} {q['progress']}/{q['goal']} — {q['coins']} coins, {q['xp']} XP" for q in rows)+"\nClaim: /claim <quest_id>")

@command("claim")
async def claim(update,context):
    if len(context.args)!=1: raise GameError("Usage: /claim <quest_id>.")
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.claim,pid,context.args[0].lower())
    if r: await reply(update,f"Quest claimed: +{r['coins']} coins, +{r['xp']} XP.")

@command("summon")
async def summon(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.summon,pid)
    if r: await reply(update,f"🎰 {r['name']} — {r['rarity']} · ATK {r['attack']} · HP {r['hp']}\n{'Duplicate converted to a shard. Total shards: '+str(r['shards']) if r['duplicate'] else 'Added to your collection.'} Cost: 80 coins.")

@command("collection")
async def collection(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); rows=await call(update,s,s.collection,pid)
    if rows is not None: await reply(update,"🧙 YOUR FIGHTERS — select with /select <id>\n"+"\n".join(f"{c['id']} — {c['name']} ({c['rarity']}) ATK {c['attack']} HP {c['hp']} · shards {c['shards']}" for c in rows))

@command("select")
async def select(update,context):
    if len(context.args)!=1: raise GameError("Usage: /select <fighter_id>. Run /collection.")
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.select,pid,context.args[0].lower())
    if r: await reply(update,f"Active fighter: {r['name']} ({r['rarity']}).")

@command("shop")
async def shop(update,context):
    s=context.application.bot_data["game"]; items=s.shop()
    await reply(update,"🛒 SHOP\n"+"\n".join(f"{i['id']} — {i['name']}: {i['description']} ({i['price']} coins)" for i in items)+"\nUse /buy <item_id> [quantity].")

@command("buy")
async def buy(update,context):
    if not 1<=len(context.args)<=2: raise GameError("Usage: /buy <item_id> [quantity].")
    try: qty=int(context.args[1]) if len(context.args)==2 else 1
    except ValueError as exc: raise GameError("Quantity must be a whole number.") from exc
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.buy,pid,context.args[0].lower(),qty)
    if r: await reply(update,f"Purchased {r['quantity']} × {r['name']} for {r['cost']} coins.")

@command("inventory")
async def inventory(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); rows=await call(update,s,s.inventory,pid)
    if rows is not None: await reply(update,"🎒 INVENTORY\n"+("\n".join(f"{i['id']} — {i['name']} ×{i['quantity']}" for i in rows) or "Empty. Browse /shop.")+"\nUse /use <item_id>.")

@command("use")
async def use_item(update,context):
    if len(context.args)!=1: raise GameError("Usage: /use <item_id>.")
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.use,pid,context.args[0].lower())
    if r: await reply(update,f"Used {r['name']}. Energy {r['energy']}/{r['max_energy']} · Level {r['level']} XP {r['xp']}.")

@command("leaderboard")
async def leaderboard(update,context):
    s=context.application.bot_data["game"]; rows=await asyncio.to_thread(s.leaderboard)
    await reply(update,"🏆 TOP FIGHTERS\n"+("\n".join(f"{i}. {r['display_name']} — Lv.{r['level']} XP {r['xp']}" for i,r in enumerate(rows,1)) or "No players yet."))

@command("clan")
async def clan(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.clan_info,pid)
    if r is None:return
    if r['clan']:
        c=r['clan']; text=f"🏰 {c['name']} (#{c['id']}) — {c['role']}\n"+"\n".join(f"• {m['display_name']} ({m['role']})" for m in r['members'])
    else: text="You are not in a clan.\n"+("\n".join(f"#{c['id']} {c['name']} — {c['members']} members" for c in r['clans']) or "No clans yet.")+"\n/clan_create <name> or /clan_join <id>"
    await reply(update,text)

@command("clan_create")
async def clan_create(update,context):
    name=" ".join(context.args)
    if not name: raise GameError("Usage: /clan_create <name>.")
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.create_clan,pid,name)
    if r: await reply(update,f"Clan {r['name']} created (ID {r['id']}).")

@command("clan_join")
async def clan_join(update,context):
    if len(context.args)!=1 or not context.args[0].isdigit(): raise GameError("Usage: /clan_join <id>.")
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.join_clan,pid,int(context.args[0]))
    if r: await reply(update,f"Joined clan {r['name']}.")

@command("clan_leave")
async def clan_leave(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.leave_clan,pid)
    if r is not None: await reply(update,"You left the clan.")

@command("clan_disband")
async def clan_disband(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.disband_clan,pid)
    if r: await reply(update,f"Clan {r} disbanded.")

@command("raid")
async def raid(update,context):
    s=context.application.bot_data["game"]; r=await asyncio.to_thread(s.raid_status); b=r['boss']
    await reply(update,f"🔱 {b['name']} — HP {b['hp']:,}/{b['max_hp']:,}\n"+"\n".join(f"{i}. {p['display_name']} — {p['damage']:,}" for i,p in enumerate(r['top'],1))+"\n/raid_attack costs 10 energy; 60-second cooldown.")

@command("raid_attack")
async def raid_attack(update,context):
    s=context.application.bot_data["game"]; pid,_,_=player(update); r=await call(update,s,s.raid_attack,pid)
    if r: await reply(update,f"Hit for {r['damage']:,}. Boss HP {r['hp']:,}/{r['max_hp']:,}."+ (" Boss defeated! +250 coins." if r['defeated'] else ""))

@command("admin_stats")
async def admin_stats(update,context):
    settings=context.application.bot_data['settings']; pid,_,_=player(update)
    if pid not in settings.admin_ids: raise GameError("Admin only.")
    s=context.application.bot_data['game']
    with s.db.reader() as con: count=con.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    await reply(update,f"Admin stats: {count} registered players.")

async def ban_cmd(update,context,banned:bool):
    settings=context.application.bot_data['settings']; actor,_,_=player(update)
    if actor not in settings.admin_ids: raise GameError("Admin only.")
    if len(context.args)!=1 or not context.args[0].isdigit(): raise GameError("Usage: /ban or /unban <telegram_id>.")
    target=int(context.args[0])
    if target in settings.admin_ids: raise GameError("You cannot ban an administrator.")
    s=context.application.bot_data['game']; r=await call(update,s,s.admin_ban,target,banned)
    if r is not None: await reply(update,f"Player {target} {'banned' if banned else 'unbanned'}.")

@command("ban")
async def ban(update,context): await ban_cmd(update,context,True)
@command("unban")
async def unban(update,context): await ban_cmd(update,context,False)

HANDLERS={"start":start,"help":help_cmd,"profile":profile,"explore":explore,"train":train,"rest":rest,"daily":daily,"quests":quests,"claim":claim,"summon":summon,"collection":collection,"select":select,"shop":shop,"buy":buy,"inventory":inventory,"use":use_item,"leaderboard":leaderboard,"clan":clan,"clan_create":clan_create,"clan_join":clan_join,"clan_leave":clan_leave,"clan_disband":clan_disband,"raid":raid,"raid_attack":raid_attack,"admin_stats":admin_stats,"ban":ban,"unban":unban}

async def post_init(app:Application):
    await app.bot.set_my_commands([BotCommand(k,k.replace('_',' ').capitalize()) for k in HANDLERS if k not in {"clan_create","clan_join","clan_leave","clan_disband","raid_attack","admin_stats","ban","unban"}])

async def on_error(update,context):
    log.error("Unhandled update failure: %s",type(context.error).__name__ if context.error else "unknown")

def build_application(settings:Settings,game:GameService):
    app=ApplicationBuilder().token(settings.bot_token).post_init(post_init).build()
    app.bot_data.update(game=game,settings=settings)
    for name,fn in HANDLERS.items(): app.add_handler(CommandHandler(name,fn))
    app.add_error_handler(on_error)
    return app
