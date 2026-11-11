from __future__ import annotations

import logging

from .advanced import register as register_advanced
from .config import load_settings
from .database import Database
from .game import GameService
from .handlers import build_application
from .market import register as register_market


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    database = Database(settings.database_path)
    database.initialize()
    game = GameService(database)
    application = build_application(settings, game)
    register_advanced(application, database)
    register_market(application, database)
    logging.getLogger(__name__).info("Starting Telegram RPG bot polling")
    application.run_polling(allowed_updates=None, close_loop=True)


if __name__ == "__main__":
    main()
import html
import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from .config import Settings
from .database import Database
from .data_catalog import ALL_CHARACTERS, BANNERS, CHARACTERS, SERIES, SKILLS
from .game import (
    GameError,
    battle_action,
    buy_asset,
    buy_shop_item,
    clan_create,
    clan_leave,
    daily_reward,
    equip_skill,
    gacha_pull,
    learn_skill,
    market_page,
    portfolio,
    profile,
    register_player,
    sell_asset,
    set_character,
    start_battle,
    use_item,
)

log = logging.getLogger(__name__)

COMMANDS = {
    "start": "Create or open your fighter profile",
    "help": "Show available commands",
    "profile": "View your stats and resources",
    "daily": "Claim today's reward",
    "characters": "Browse the character catalog",
    "character": "Inspect a character",
    "team": "View owned fighters",
    "quipchar": "Choose your active fighter",
    "shop": "Buy items from the shop",
    "inventory": "Check your inventory",
    "skills": "View your skills",
    "learn": "Learn a new skill",
    "gacha": "Open a pull banner",
    "pull": "Pull once on a banner",
    "hunt": "Start a manual turn-based hunt",
    "explore": "Start a manual encounter",
    "dungeon": "Start a manual dungeon battle",
    "market": "Browse the Capsule Corp. exchange",
    "portfolio": "View exchange holdings",
    "sell": "Sell an exchange asset",
    "clan": "Check clan information",
    "clan_create": "Create a clan",
    "clan_leave": "Leave your clan",
    "use": "Use a consumable item",
}
HELP = "🐉 Dragon Ball RPG\n\n" + "\n".join(f"/{k} — {v}" for k, v in COMMANDS.items()) + "\n\nAdmin: /add (ADMIN_IDS only). Battles are manual; choose every turn."


async def ensure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None:
        raise GameError("Could not identify your Telegram account.")
    return await register_player(context.application.bot_data["db"], user.id, user.username, user.full_name or "Fighter")


async def reply(update: Update, text: str, **kwargs):
    if update.effective_message:
        await update.effective_message.reply_text(text, **kwargs)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await ensure(update, context)
    await reply(update, f"🐉 Dragon Ball RPG\nWelcome, {html.escape(player['display_name'])}! Type /help to begin.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    await reply(update, HELP)


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = await ensure(update, context)
    bar = "█" * min(10, p["xp"] % 100 // 10) + "░" * (10 - min(10, p["xp"] % 100 // 10))
    await reply(
        update,
        f"👤 {html.escape(p['display_name'])} · ID {p['telegram_id']}\n"
        f"Level {p['level']} · XP {p['xp']} [{bar}]\n"
        f"💴 {p['coins']:,} Zeni · 💎 {p['gems']:,} gems\n"
        f"⚡ Energy {p['energy']}/{p['max_energy']}\n"
        f"STR {p['str_stat']} · AGI {p['agi_stat']} · INT {p['int_stat']} · VIT {p['vit_stat']} · LUK {p['luk_stat']} · points {p['stat_points']}\n"
        f"🌍 Region: {html.escape(p['region'])}\nPvE wins {p['pve_wins']} · PvP wins {p['pvp_wins']} · Explores {p['explores']}",
    )


async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    result = await daily_reward(context.application.bot_data["db"], update.effective_user.id)
    await reply(update, f"🎁 Daily reward claimed: {result['coins']} Zeni · streak {result['streak']} day(s).")


async def characters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    rows = [[InlineKeyboardButton(f"{v['icon']} {name}", callback_data=f"series:{i}")] for i, (name, v) in enumerate(SERIES.items())]
    await reply(update, "Choose a series:", reply_markup=InlineKeyboardMarkup(rows))


async def show_character(update: Update, character: dict, *, query=None):
    from .data_catalog import RARITY_ICONS
    text = (
        f"{html.escape(character['name'])} [{character['rank']}]\n"
        f"Series: {html.escape(character['series'])}\n"
        f"Rarity: {RARITY_ICONS.get(character['rarity'], '★')} · Element: {html.escape(character['element'])}\n"
        f"Trait: {html.escape(character['trait'])}\nAbility: {html.escape(character['ability'])}\n"
        f"Base HP {character['hp']} · ATK {character['attack']}"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Equip if owned", callback_data=f"char:select:{character['id']}")]])
    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)


async def character_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    if context.args:
        key = " ".join(context.args).casefold()
        found = next((c for c in ALL_CHARACTERS if c["id"] == key or c["name"].casefold() == key), None)
        if found:
            await show_character(update, found)
            return
    rows = [[InlineKeyboardButton(f"{c['name']} [{c['rank']}]", callback_data=f"char:view:{c['id']}")] for c in ALL_CHARACTERS[:50]]
    await reply(update, "Choose a character to inspect:", reply_markup=InlineKeyboardMarkup(rows))


async def team_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = await ensure(update, context)
    db = context.application.bot_data["db"]
    con = await db.connect()
    try:
        cur = await con.execute("SELECT character_id, level FROM owned_characters WHERE player_id=? ORDER BY character_id", (p["telegram_id"],))
        owned = await cur.fetchall()
    finally:
        await con.close()

    if not owned:
        await reply(update, "No fighters owned yet.")
        return

    buttons = [[InlineKeyboardButton(f"{CHARACTERS.get(r['character_id'], {}).get('name', r['character_id'])} · Lv {r['level']}", callback_data=f"char:select:{r['character_id']}")] for r in owned]
    await reply(update, f"Active fighter: {html.escape(p['active_character'])}\nTap a fighter to equip:", reply_markup=InlineKeyboardMarkup(buttons))


def bar(value: int, maximum: int) -> str:
    filled = max(0, min(10, int(10 * value / max(1, maximum))))
    return "█" * filled + "░" * (10 - filled)


def battle_text(b: dict) -> str:
    return (
        f"⚔️ <b>{html.escape(b['kind'].title())}: {html.escape(b['enemy'])}</b> · Turn {b['turn'] + 1}\n"
        f"❤️ You {bar(b['player_hp'], b['player_max_hp'])} {b['player_hp']}/{b['player_max_hp']}\n"
        f"🔵 MP {b['mp']}/100 · 🌟 ULT {b['ult']}%\n"
        f"👹 Enemy {bar(b['enemy_hp'], b['enemy_max_hp'])} {b['enemy_hp']}/{b['enemy_max_hp']}\nChoose your move. The enemy only acts after your choice."
    )


def battle_markup(bid: int) -> InlineKeyboardMarkup:
    actions = [
        ("⚔️ Attack", "attack"), ("🌀 Dodge", "dodge"), ("💥 Skill 1", "skill1"),
        ("✨ Skill 2", "skill2"), ("🔥 Transform", "transform"), ("🔄 Switch", "switch"),
        ("🏃 Flee", "flee"),
    ]
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f"battle:{bid}:{action}") for label, action in actions[i:i+2]] for i in range(0, len(actions), 2)])


async def battle_start(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    await ensure(update, context)
    battle = await start_battle(context.application.bot_data["db"], update.effective_user.id, kind)
    await reply(update, battle_text(battle), parse_mode="HTML", reply_markup=battle_markup(battle["id"]))


async def hunt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await battle_start(update, context, "hunt")


async def explore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await battle_start(update, context, "explore")


async def dungeon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await battle_start(update, context, "dungeon")


async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = await ensure(update, context)
    rows, page, pages = await market_page(context.application.bot_data["db"])
    await send_market(update, rows, page, pages, p["coins"])


async def send_market(update, rows, page, pages, coins, query=None):
    lines = [f"🏢 <b>CAPSULE CORP. EXCHANGE</b> · {coins:,} Zeni · 1% fee\nPrices move every 5 minutes; values can fall."]
    buttons = []
    for r in rows:
        lines.append(f"\n{r['emoji']} <b>{html.escape(r['name'])}</b> · {r['price']:,} Zeni · {r['change_pct']:+.1f}% · stock {r['stock']}")
        buttons.append([InlineKeyboardButton(f"Buy {r['asset_id']} · {r['price']:,}", callback_data=f"market:asset:{r['asset_id']}")])
    nav = []
    if page:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"market:page:{page-1}"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"market:page:{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("💼 Portfolio", callback_data="market:portfolio")])
    text = "\n".join(lines) + f"\n\nPage {page + 1}/{pages}"
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    await reply(update, await portfolio(context.application.bot_data["db"], update.effective_user.id), parse_mode="HTML")


async def sell_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    db = context.application.bot_data["db"]
    con = await db.connect()
    try:
        cur = await con.execute("SELECT p.asset_id, p.quantity, a.name FROM market_positions p JOIN market_assets a ON a.asset_id = p.asset_id WHERE p.player_id=? AND p.quantity>0 ORDER BY a.name", (update.effective_user.id,))
        rows = await cur.fetchall()
    finally:
        await con.close()
    if not rows:
        await reply(update, "Your exchange portfolio is empty.")
        return
    buttons = [[InlineKeyboardButton(f"Sell {r['name']} ×{r['quantity']}", callback_data=f"market:sell:{r['asset_id']}:1")] for r in rows]
    await reply(update, "Choose an asset to sell:", reply_markup=InlineKeyboardMarkup(buttons))


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    from .data_catalog import ITEMS
    buttons = [[InlineKeyboardButton(f"{v['name']} ({v['price']} Zeni)", callback_data=f"shop:buy:{k}")] for k, v in ITEMS.items()]
    await reply(update, "Choose an item to buy:", reply_markup=InlineKeyboardMarkup(buttons))


async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    db = context.application.bot_data["db"]
    con = await db.connect()
    try:
        cur = await con.execute("SELECT item_id, quantity FROM owned_items WHERE player_id=? ORDER BY item_id", (update.effective_user.id,))
        rows = await cur.fetchall()
    finally:
        await con.close()
    if not rows:
        await reply(update, "Your inventory is empty. Visit /shop to buy items.")
        return
    lines = ["🎒 Inventory:"]
    for row in rows:
        lines.append(f"- {row['item_id']}: {row['quantity']}")
    await reply(update, "\n".join(lines))


async def skills_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    db = context.application.bot_data["db"]
    con = await db.connect()
    try:
        cur = await con.execute("SELECT skill_id, slot FROM owned_skills WHERE player_id=? ORDER BY skill_id", (update.effective_user.id,))
        rows = await cur.fetchall()
    finally:
        await con.close()
    if not rows:
        await reply(update, "No skills unlocked yet. Use /learn to train a new technique.")
        return
    lines = ["⚔️ Skills:"]
    for row in rows:
        lines.append(f"- {row['skill_id']} · slot {row['slot'] or 'unassigned'}")
    await reply(update, "\n".join(lines))


async def learn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    from .data_catalog import SKILLS
    buttons = [[InlineKeyboardButton(f"{v['name']} ({max(30, v['mp_cost'] * 4)} Zeni)", callback_data=f"skill:learn:{k}")] for k, v in SKILLS.items()]
    await reply(update, "Choose a skill to learn:", reply_markup=InlineKeyboardMarkup(buttons))


async def gacha_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    buttons = [[InlineKeyboardButton(f"{v['name']} ({v['cost']} Zeni)", callback_data=f"gacha:pull:{k}")] for k, v in BANNERS.items()]
    await reply(update, "Choose a banner:", reply_markup=InlineKeyboardMarkup(buttons))


async def pull_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    if not context.args:
        await gacha_cmd(update, context)
        return
    banner = context.args[0].lower()
    result = await gacha_pull(context.application.bot_data["db"], update.effective_user.id, banner)
    if result.get("duplicate"):
        await reply(update, f"✨ Duplicate draw! {result['reward']} returned to the banner, and you received {result['bonus_gems']} gems as a reward.")
    else:
        await reply(update, f"🎉 New fighter: {result['reward']}. Banner: {result['banner']}")


async def clan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    db = context.application.bot_data["db"]
    con = await db.connect()
    try:
        row = await (await con.execute("SELECT c.name, cm.role FROM clan_members cm JOIN clans c ON c.id = cm.clan_id WHERE cm.player_id=?", (update.effective_user.id,))).fetchone()
    finally:
        await con.close()
    if not row:
        await reply(update, "You are not in a clan. Use /clan_create <name> to create one.")
        return
    await reply(update, f"👑 Clan: {row['name']}\nRole: {row['role']}")


async def clan_create_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    if not context.args:
        await reply(update, "Use /clan_create <ClanName>")
        return
    result = await clan_create(context.application.bot_data["db"], update.effective_user.id, " ".join(context.args))
    await reply(update, f"✅ Clan created: {result['clan_name']}")


async def clan_leave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    result = await clan_leave(context.application.bot_data["db"], update.effective_user.id)
    if result["leader_disbanded"]:
        await reply(update, f"💥 You were the leader, so clan {result['clan_name']} was disbanded.")
    else:
        await reply(update, f"✅ You left clan {result['clan_name']}.")


async def use_item_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure(update, context)
    if not context.args:
        from .data_catalog import ITEMS
        buttons = [[InlineKeyboardButton(f"{v['name']}", callback_data=f"item:use:{item_id}")] for item_id, v in ITEMS.items() if v["category"] == "consumable"]
        await reply(update, "Choose an item to use:", reply_markup=InlineKeyboardMarkup(buttons))
        return
    result = await use_item(context.application.bot_data["db"], update.effective_user.id, context.args[0].lower())
    await reply(update, f"✅ Used {result['name']} and gained {result['amount']} {result['effect']}.")


async def market_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    parts = (q.data or "").split(":")
    db = context.application.bot_data["db"]

    if len(parts) == 3 and parts[1] == "page":
        rows, page, pages = await market_page(db, int(parts[2]))
        p = await profile(db, q.from_user.id)
        await send_market(update, rows, page, pages, p["coins"], q)
    elif parts == ["market", "portfolio"]:
        await q.edit_message_text(await portfolio(db, q.from_user.id), parse_mode="HTML")
    elif len(parts) == 3 and parts[1] == "asset":
        asset_id = parts[2]
        buttons = [[InlineKeyboardButton(f"Buy {n}", callback_data=f"market:buy:{asset_id}:{n}") for n in (1, 5, 10)], [InlineKeyboardButton("Cancel", callback_data="market:back")]]
        await q.edit_message_text(f"Select quantity for {html.escape(asset_id)}. Current quote may change before purchase.", reply_markup=InlineKeyboardMarkup(buttons))
    elif len(parts) == 4 and parts[1] == "buy":
        result = await buy_asset(db, q.from_user.id, parts[2], int(parts[3]))
        await q.edit_message_text(f"✅ Bought {result['quantity']} × {html.escape(result['name'])} for {result['total']:,} Zeni (fee {result['fee']:,}).")
    elif len(parts) == 4 and parts[1] == "sell":
        result = await sell_asset(db, q.from_user.id, parts[2], int(parts[3]))
        await q.edit_message_text(f"✅ Sold {result['quantity']} × {html.escape(result['name'])} for {result['proceeds']:,} Zeni after fee. P/L {result['realized']:+,}.")
    elif parts == ["market", "back"]:
        rows, page, pages = await market_page(db)
        p = await profile(db, q.from_user.id)
        await send_market(update, rows, page, pages, p["coins"], q)
    else:
        await q.edit_message_text("That market action is not available.")


async def battle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    parts = (q.data or "").split(":")
    if len(parts) != 3:
        await q.edit_message_text("Invalid battle action.")
        return

    result = await battle_action(context.application.bot_data["db"], q.from_user.id, int(parts[1]), parts[2])
    if result["finished"]:
        await q.edit_message_text(result["text"])
        return

    con = await context.application.bot_data["db"].connect()
    try:
        row = await (await con.execute("SELECT * FROM active_battles WHERE id=? AND player_id=?", (int(parts[1]), q.from_user.id))).fetchone()
        battle = dict(row)
    finally:
        await con.close()
    await q.edit_message_text(f"You dealt {result['dealt']} · received {result['damage']} damage.\n\n{battle_text(battle)}", parse_mode="HTML", reply_markup=battle_markup(battle["id"]))


async def character_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    parts = (q.data or "").split(":")
    if len(parts) != 3:
        await q.edit_message_text("Invalid selection.")
        return

    if parts[1] == "view":
        c = CHARACTERS.get(parts[2])
        if not c:
            await q.edit_message_text("Character not found.")
            return
        await show_character(update, c, query=q)
    elif parts[1] == "select":
        await set_character(context.application.bot_data["db"], q.from_user.id, parts[2])
        await q.edit_message_text(f"✅ Active fighter set to {html.escape(CHARACTERS.get(parts[2], {}).get('name', parts[2]))}.")
    else:
        await q.edit_message_text("Invalid selection.")


async def series_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    try:
        series = list(SERIES)[int((q.data or "").split(":")[1])]
    except (IndexError, ValueError):
        await q.edit_message_text("Series not found.")
        return
    chars = [CHARACTERS[k] for k in SERIES[series]["characters"] if k in CHARACTERS]
    rows = [[InlineKeyboardButton(f"[{c['rank']}] {c['name']}", callback_data=f"char:view:{c['id']}")] for c in chars]
    await q.edit_message_text(f"{series} · choose a character:", reply_markup=InlineKeyboardMarkup(rows))


async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    parts = (q.data or "").split(":")
    if len(parts) == 3 and parts[1] == "buy":
        result = await buy_shop_item(context.application.bot_data["db"], q.from_user.id, parts[2], 1)
        await q.edit_message_text(f"✅ Purchased {result['name']} for {result['total']:,} Zeni.")


async def skill_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    parts = (q.data or "").split(":")
    if len(parts) == 3 and parts[1] == "learn":
        result = await learn_skill(context.application.bot_data["db"], q.from_user.id, parts[2])
        await q.edit_message_text(f"✅ Learned {result['name']} for {result['cost']:,} Zeni.")


async def gacha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    parts = (q.data or "").split(":")
    if len(parts) == 3 and parts[1] == "pull":
        result = await gacha_pull(context.application.bot_data["db"], q.from_user.id, parts[2])
        if result.get("duplicate"):
            await q.edit_message_text(f"✨ Duplicate draw! {result['reward']} returned to the banner, and you received {result['bonus_gems']} gems as a reward.")
        else:
            await q.edit_message_text(f"🎉 New fighter: {result['reward']}.")


async def item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await ensure(update, context)
    parts = (q.data or "").split(":")
    if len(parts) == 3 and parts[1] == "use":
        result = await use_item(context.application.bot_data["db"], q.from_user.id, parts[2])
        await q.edit_message_text(f"✅ Used {result['name']} and gained {result['amount']} {result['effect']}.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if isinstance(error, GameError):
        target = getattr(update, "effective_message", None)
        query = getattr(update, "callback_query", None)
        try:
            if query:
                await query.answer(str(error)[:180], show_alert=True)
            elif target:
                await target.reply_text(str(error))
        except Exception:
            log.exception("Could not report game error")
        return
    log.exception("Unhandled Telegram handler error", exc_info=error)
    query = getattr(update, "callback_query", None)
    target = getattr(update, "effective_message", None)
    try:
        if query:
            await query.answer("Something went wrong. Please retry.", show_alert=True)
        elif target:
            await target.reply_text("Something went wrong. Please retry.")
    except Exception:
        log.exception("Could not report handler error")


async def post_init(application: Application):
    await application.bot.set_my_commands([BotCommand(name, description[:256]) for name, description in COMMANDS.items()])


def build_application(settings: Settings, db: Database) -> Application:
    app = ApplicationBuilder().token(settings.bot_token).post_init(post_init).build()
    app.bot_data.update(settings=settings, db=db)

    handlers = [
        ("start", start), ("help", help_cmd), ("profile", profile_cmd), ("daily", daily_cmd),
        ("characters", characters_cmd), ("character", character_cmd), ("team", team_cmd), ("equipchar", team_cmd),
        ("shop", shop_cmd), ("inventory", inventory_cmd), ("skills", skills_cmd), ("learn", learn_cmd),
        ("gacha", gacha_cmd), ("pull", pull_cmd), ("hunt", hunt_cmd), ("explore", explore_cmd), ("dungeon", dungeon_cmd),
        ("market", market_cmd), ("portfolio", portfolio_cmd), ("sell", sell_cmd),
        ("clan", clan_cmd), ("clan_create", clan_create_cmd), ("clan_leave", clan_leave_cmd),
        ("use", use_item_cmd),
    ]
    for name, callback in handlers:
        app.add_handler(CommandHandler(name, callback))

    app.add_handler(CallbackQueryHandler(battle_callback, pattern=r"^battle:"))
    app.add_handler(CallbackQueryHandler(market_callback, pattern=r"^market:"))
    app.add_handler(CallbackQueryHandler(character_callback, pattern=r"^char:"))
    app.add_handler(CallbackQueryHandler(series_callback, pattern=r"^series:"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(skill_callback, pattern=r"^skill:"))
    app.add_handler(CallbackQueryHandler(gacha_callback, pattern=r"^gacha:"))
    app.add_handler(CallbackQueryHandler(item_callback, pattern=r"^item:"))
    app.add_error_handler(error_handler)
    return app


__all__ = ["build_application", "COMMANDS", "HELP"]
