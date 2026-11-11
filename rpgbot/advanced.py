from __future__ import annotations

"""Tap-first interactive battles and admin art tools for the RPG foundation."""

import asyncio
import html
import logging
import random
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from .catalog import CHARACTERS, ENEMIES
from .config import Settings
from .database import Database
from .game import GameError, GameService

log = logging.getLogger(__name__)


def initialize(db: Database) -> None:
    with db.transaction() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS active_battles(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          player_id INTEGER NOT NULL REFERENCES players(telegram_id) ON DELETE CASCADE,
          kind TEXT NOT NULL, enemy TEXT NOT NULL, enemy_hp INTEGER NOT NULL,
          enemy_max_hp INTEGER NOT NULL, player_hp INTEGER NOT NULL,
          player_max_hp INTEGER NOT NULL, mp INTEGER NOT NULL DEFAULT 100,
          ult INTEGER NOT NULL DEFAULT 0, transformed INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'active', turn INTEGER NOT NULL DEFAULT 0,
          created_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_battles_player_status ON active_battles(player_id,status);
        CREATE TABLE IF NOT EXISTS custom_art(
          entity_key TEXT PRIMARY KEY, file_id TEXT NOT NULL, uploaded_by INTEGER NOT NULL,
          updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS battle_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INTEGER NOT NULL,
          enemy TEXT NOT NULL, result TEXT NOT NULL, turns INTEGER NOT NULL,
          created_at INTEGER NOT NULL);
        """)


def _bar(value: int, maximum: int, width: int = 12) -> str:
    maximum = max(1, maximum)
    filled = max(0, min(width, int(width * value / maximum)))
    return "█" * filled + "░" * (width - filled)


def _battle_markup(battle_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Attack", callback_data=f"rpg:b:{battle_id}:attack"),
         InlineKeyboardButton("🌀 Dodge", callback_data=f"rpg:b:{battle_id}:dodge")],
        [InlineKeyboardButton("💥 Skill 1", callback_data=f"rpg:b:{battle_id}:skill1"),
         InlineKeyboardButton("✨ Skill 2", callback_data=f"rpg:b:{battle_id}:skill2")],
        [InlineKeyboardButton("🔥 Transform", callback_data=f"rpg:b:{battle_id}:transform"),
         InlineKeyboardButton("🔄 Switch", callback_data=f"rpg:b:{battle_id}:switch")],
        [InlineKeyboardButton("🏃 Flee", callback_data=f"rpg:b:{battle_id}:flee")],
    ])


def _battle_text(row, fighter: str) -> str:
    return (f"⚔️ <b>{html.escape(row['kind'].title())}: {html.escape(row['enemy'])}</b>\n"
            f"Turn {row['turn'] + 1} · Fighter: {html.escape(fighter)}\n\n"
            f"❤️ You  {_bar(row['player_hp'], row['player_max_hp'])}  {row['player_hp']}/{row['player_max_hp']}\n"
            f"🔵 MP   {_bar(row['mp'], 100)}  {row['mp']}/100\n"
            f"🌟 ULT  {_bar(row['ult'], 100)}  {row['ult']}%\n\n"
            f"👹 Enemy {_bar(row['enemy_hp'], row['enemy_max_hp'])}  {row['enemy_hp']}/{row['enemy_max_hp']}\n\n"
            "Choose every move manually:")


async def _safe_reply(update: Update, text: str, **kwargs) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(text, **kwargs)


async def auto_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a profile before any command that needs one; /start remains idempotent."""
    user = update.effective_user
    if user is None:
        return
    service: GameService = context.application.bot_data["game"]
    try:
        await asyncio.to_thread(service.register, user.id, user.username, user.full_name or "Fighter")
    except GameError:
        # Banned users still receive the command's normal player-facing restriction.
        pass


async def launch(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    service: GameService = context.application.bot_data["game"]
    user = update.effective_user
    if user is None:
        raise GameError("Could not identify your Telegram account.")
    await asyncio.to_thread(service.register, user.id, user.username, user.full_name or "Fighter")
    db = service.db
    with db.transaction() as con:
        p = service.require(con, user.id)
        active = con.execute("SELECT id FROM active_battles WHERE player_id=? AND status='active'", (user.id,)).fetchone()
        if active:
            row = con.execute("SELECT * FROM active_battles WHERE id=?", (active["id"],)).fetchone()
            fighter = CHARACTERS.get(p["active_character"], CHARACTERS["goku"])
            message = _battle_text(row, fighter["name"])
            battle_id = row["id"]
        else:
            if p["energy"] < 10:
                raise GameError("You need 10 energy to start an encounter. Use /rest or an energy item.")
            enemy = random.choice(ENEMIES)
            fighter = CHARACTERS.get(p["active_character"], CHARACTERS["goku"])
            max_hp = fighter["hp"] + p["level"] * 4
            enemy_hp = enemy["hp"] + p["level"] * 8
            con.execute("UPDATE players SET energy=energy-10 WHERE telegram_id=?", (user.id,))
            cur = con.execute("INSERT INTO active_battles(player_id,kind,enemy,enemy_hp,enemy_max_hp,player_hp,player_max_hp,created_at) VALUES(?,?,?,?,?,?,?,?)",
                              (user.id, kind, enemy["name"], enemy_hp, enemy_hp, max_hp, max_hp, int(time.time())))
            battle_id = cur.lastrowid
            row = con.execute("SELECT * FROM active_battles WHERE id=?", (battle_id,)).fetchone()
            message = _battle_text(row, fighter["name"])
    await _safe_reply(update, message, parse_mode="HTML", reply_markup=_battle_markup(battle_id))


async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await launch(update, context, "hunt")


async def dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await launch(update, context, "dungeon")


async def character_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service: GameService = context.application.bot_data["game"]
    user = update.effective_user
    if not user:
        return
    await asyncio.to_thread(service.register, user.id, user.username, user.full_name or "Fighter")
    owned = await asyncio.to_thread(service.collection, user.id)
    if context.args:
        requested = " ".join(context.args).lower()
        key = next((k for k, v in CHARACTERS.items() if k == requested or v["name"].lower() == requested), None)
        if key is None:
            await _safe_reply(update, "Unknown fighter. Use /characters to browse your roster.")
            return
        character = CHARACTERS[key]
        text = (f"🧙 <b>{html.escape(character['name'])}</b> · {character['rarity']}\n"
                f"Series: Dragon Ball · Element: Ki · Trait: Resolute\nAbility: Energy strike\n"
                f"Forms: Base\n❤️ HP {character['hp']} · ⚔️ ATK {character['attack']}")
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Equip character", callback_data=f"rpg:char:select:{key}")]]) if any(x["id"] == key for x in owned) else None
        art = await asyncio.to_thread(get_art, service.db, key)
        if art and update.effective_message:
            await update.effective_message.reply_photo(art, caption=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await _safe_reply(update, text, parse_mode="HTML", reply_markup=keyboard)
        return
    buttons = [[InlineKeyboardButton(f"{c['name']} · {c['rarity']}", callback_data=f"rpg:char:inspect:{c['id']}")] for c in owned]
    if not buttons:
        await _safe_reply(update, "No fighters yet. Use /summon to recruit one.")
    else:
        await _safe_reply(update, "Choose a fighter to inspect:", reply_markup=InlineKeyboardMarkup(buttons))


def get_art(db: Database, key: str):
    with db.reader() as con:
        row = con.execute("SELECT file_id FROM custom_art WHERE entity_key=?", (key.lower(),)).fetchone()
        return row["file_id"] if row else None


async def crown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not update.effective_user or update.effective_user.id not in settings.admin_ids:
        await _safe_reply(update, "Admin only.")
        return
    categories = {
        "heroes": list(CHARACTERS),
        "npcs": [x["name"] for x in ENEMIES],
        "boss": ["world_eater"],
        "summons": ["elite", "boss"],
        "map": ["earth", "namek", "other_world"],
    }
    selected = context.args[0].lower() if context.args else "heroes"
    if selected not in categories:
        await _safe_reply(update, "Choose: /crown heroes, /crown npcs, /crown boss, /crown summons, or /crown map")
        return
    db = context.application.bot_data["game"].db
    rows = await asyncio.to_thread(art_checklist, db, categories[selected])
    have = sum(1 for _, exists in rows if exists)
    title = selected[:-1].title() if selected.endswith("s") else selected.title()
    listing = "\n".join(("✅ " if ok else "❌ ") + str(name).replace("_", " ").title() for name, ok in rows)
    tabs = [[InlineKeyboardButton(name.title(), callback_data=f"rpg:crown:{name}") for name in categories]]
    await _safe_reply(update, f"👑 Crown · {title} — {have}/{len(rows)} have art\n{listing}\n\nUpload: reply to a photo with /upload NAME",
                      reply_markup=InlineKeyboardMarkup(tabs))


def art_checklist(db: Database, names):
    with db.reader() as con:
        return [(name, bool(con.execute("SELECT 1 FROM custom_art WHERE entity_key=?", (str(name).lower(),)).fetchone())) for name in names]


async def upload_art(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    message = update.effective_message
    if not user or user.id not in settings.admin_ids:
        await _safe_reply(update, "Admin only.")
        return
    if not message or not message.reply_to_message or not message.reply_to_message.photo or not context.args:
        await _safe_reply(update, "Reply to a photo with /upload <entity_name>.")
        return
    key = " ".join(context.args).strip().lower()
    await asyncio.to_thread(save_art, context.application.bot_data["game"].db, key,
                            message.reply_to_message.photo[-1].file_id, user.id)
    await _safe_reply(update, f"✅ Art saved for {html.escape(key)}.")


def save_art(db: Database, key: str, file_id: str, user_id: int) -> None:
    with db.transaction() as con:
        con.execute("INSERT INTO custom_art(entity_key,file_id,uploaded_by,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(entity_key) DO UPDATE SET file_id=excluded.file_id,uploaded_by=excluded.uploaded_by,updated_at=excluded.updated_at",
                    (key, file_id, user_id, int(time.time())))


async def clan_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service: GameService = context.application.bot_data["game"]
    user = update.effective_user
    if not user:
        return
    await asyncio.to_thread(service.register, user.id, user.username, user.full_name or "Fighter")
    with service.db.reader() as con:
        member = con.execute("SELECT m.clan_id,m.role,c.name FROM clan_members m JOIN clans c ON c.id=m.clan_id WHERE m.player_id=?", (user.id,)).fetchone()
        if not member:
            await _safe_reply(update, "You are not in a clan.")
            return
        others = [dict(r) for r in con.execute("SELECT p.telegram_id,p.display_name FROM clan_members m JOIN players p ON p.telegram_id=m.player_id WHERE m.clan_id=? AND m.player_id<>?", (member["clan_id"], user.id))]
    if member["role"] == "leader":
        buttons = [[InlineKeyboardButton(f"👑 Promote {m['display_name']}", callback_data=f"rpg:clan:transfer:{m['telegram_id']}")] for m in others]
        buttons.append([InlineKeyboardButton("💥 Disband Clan", callback_data="rpg:clan:disband_confirm")])
        await _safe_reply(update, "Clan leaders cannot leave while leading. Transfer leadership or disband the clan:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yes, Leave", callback_data="rpg:clan:leave_yes"), InlineKeyboardButton("❌ Cancel", callback_data="rpg:clan:cancel")]])
        await _safe_reply(update, f"⚠️ Are you sure you want to leave {member['name']}?", reply_markup=markup)


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    service: GameService = context.application.bot_data["game"]
    uid = query.from_user.id
    try:
        if len(parts) == 4 and parts[1] == "b":
            result = await asyncio.to_thread(battle_action, service.db, uid, int(parts[2]), parts[3])
            if result["finished"]:
                await query.edit_message_text(result["text"], parse_mode="HTML")
            else:
                await query.edit_message_text(result["text"], parse_mode="HTML", reply_markup=_battle_markup(int(parts[2])))
        elif parts[:2] == ["rpg", "char"] and len(parts) == 4:
            action, key = parts[2], parts[3]
            if action == "select":
                character = await asyncio.to_thread(service.select, uid, key)
                await query.edit_message_text(f"✅ Active fighter: {html.escape(character['name'])}.")
            elif action == "inspect":
                c = CHARACTERS[key]
                await query.edit_message_text(f"🧙 {html.escape(c['name'])} · {c['rarity']}\nHP {c['hp']} · ATK {c['attack']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Equip", callback_data=f"rpg:char:select:{key}")]]))
        elif parts[:3] == ["rpg", "crown", parts[2]] and len(parts) == 3:
            await query.edit_message_text("Use /crown " + parts[2] + " to view this category.")
        elif parts[:3] == ["rpg", "clan", "leave_yes"]:
            await asyncio.to_thread(service.leave_clan, uid)
            await query.edit_message_text("You left the clan.")
        elif parts[:3] == ["rpg", "clan", "cancel"]:
            await query.edit_message_text("Clan action cancelled.")
        elif len(parts) == 4 and parts[:3] == ["rpg", "clan", "transfer"]:
            await asyncio.to_thread(transfer_leader, service.db, uid, int(parts[3]))
            await query.edit_message_text("Leadership transferred.")
        elif parts[:3] == ["rpg", "clan", "disband_confirm"]:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("💥 Confirm disband", callback_data="rpg:clan:disband_yes"), InlineKeyboardButton("Cancel", callback_data="rpg:clan:cancel")]])
            await query.edit_message_text("Confirm clan disband? This removes the clan and its membership.", reply_markup=markup)
        elif parts[:3] == ["rpg", "clan", "disband_yes"]:
            name = await asyncio.to_thread(service.disband_clan, uid)
            await query.edit_message_text(f"Clan {html.escape(name)} disbanded.")
    except (GameError, KeyError, ValueError) as exc:
        await query.edit_message_text(str(exc))
    except Exception as exc:
        log.exception("Interactive callback failed: %s", type(exc).__name__)
        await query.edit_message_text("This action could not be completed. Please try again.")


def transfer_leader(db: Database, actor: int, target: int) -> None:
    with db.transaction() as con:
        clan = con.execute("SELECT clan_id,role FROM clan_members WHERE player_id=?", (actor,)).fetchone()
        other = con.execute("SELECT clan_id,role FROM clan_members WHERE player_id=?", (target,)).fetchone()
        if not clan or clan["role"] != "leader" or not other or other["clan_id"] != clan["clan_id"]:
            raise GameError("Only the clan leader can transfer leadership to a current member.")
        con.execute("UPDATE clan_members SET role='officer' WHERE player_id=?", (actor,))
        con.execute("UPDATE clan_members SET role='leader' WHERE player_id=?", (target,))
        con.execute("UPDATE clans SET leader_id=? WHERE id=?", (target, clan["clan_id"]))


def battle_action(db: Database, uid: int, battle_id: int, action: str):
    with db.transaction() as con:
        row = con.execute("SELECT * FROM active_battles WHERE id=? AND player_id=?", (battle_id, uid)).fetchone()
        if not row or row["status"] != "active":
            raise GameError("This battle is no longer active.")
        player = con.execute("SELECT level,active_character FROM players WHERE telegram_id=?", (uid,)).fetchone()
        fighter = CHARACTERS.get(player["active_character"], CHARACTERS["goku"])
        hp, enemy_hp, mp, ult = row["player_hp"], row["enemy_hp"], row["mp"], row["ult"]
        transformed = row["transformed"]
        if action == "flee":
            con.execute("UPDATE active_battles SET status='fled' WHERE id=?", (battle_id,))
            con.execute("INSERT INTO battle_history(player_id,enemy,result,turns,created_at) VALUES(?,?,?,?,?)", (uid,row["enemy"],"fled",row["turn"],int(time.time())))
            return {"finished":True,"text":f"🏃 You fled from {html.escape(row['enemy'])}. No battle reward was granted."}
        damage = max(1, int((fighter["attack"] + player["level"] * 3) * random.uniform(.85,1.15)))
        dodge = action == "dodge"
        if action == "skill1":
            if mp < 20: raise GameError("Skill 1 costs 20 MP.")
            mp -= 20; damage = int(damage * 1.7)
        elif action == "skill2":
            if mp < 35: raise GameError("Skill 2 costs 35 MP.")
            mp -= 35; damage = int(damage * 2.2); hp = min(row["player_max_hp"],hp+10)
        elif dodge:
            mp = min(100,mp+15)
        elif action == "transform":
            if transformed: raise GameError("You have already transformed in this battle.")
            transformed=1; damage=int(damage*1.5); ult=min(100,ult+20)
        elif action == "switch":
            damage=max(1,int(damage*.65)); mp=min(100,mp+10)
        elif action != "attack":
            raise GameError("Unknown battle action.")
        if not dodge:
            enemy_hp=max(0,enemy_hp-damage); ult=min(100,ult+15)
        turn=row["turn"]+1
        if enemy_hp<=0:
            con.execute("UPDATE active_battles SET status='won',enemy_hp=0,player_hp=?,mp=?,ult=?,turn=? WHERE id=?",(hp,mp,ult,turn,battle_id))
            con.execute("UPDATE players SET coins=coins+25 WHERE telegram_id=?",(uid,))
            GameService.award_xp(con,uid,30)
            con.execute("INSERT INTO battle_history(player_id,enemy,result,turns,created_at) VALUES(?,?,?,?,?)",(uid,row["enemy"],"won",turn,int(time.time())))
            return {"finished":True,"text":f"🏆 Victory! {html.escape(row['enemy'])} defeated after {turn} turns.\nYou earned 25 coins and 30 XP. Use /hunt to begin another encounter."}
        enemy_dmg=next((x["attack"] for x in ENEMIES if x["name"]==row["enemy"]),12)
        taken=0 if dodge else max(1,int(enemy_dmg*random.uniform(.8,1.2)))
        hp=max(0,hp-taken)
        if hp<=0:
            con.execute("UPDATE active_battles SET status='lost',player_hp=0,enemy_hp=?,turn=? WHERE id=?",(enemy_hp,turn,battle_id))
            con.execute("INSERT INTO battle_history(player_id,enemy,result,turns,created_at) VALUES(?,?,?,?,?)",(uid,row["enemy"],"lost",turn,int(time.time())))
            return {"finished":True,"text":f"💫 Defeat! {html.escape(row['enemy'])} won after {turn} turns. Train and return with /hunt."}
        con.execute("UPDATE active_battles SET player_hp=?,enemy_hp=?,mp=?,ult=?,transformed=?,turn=? WHERE id=?",(hp,enemy_hp,mp,ult,transformed,turn,battle_id))
        fresh=con.execute("SELECT * FROM active_battles WHERE id=?",(battle_id,)).fetchone()
        intro="You dodged and recovered 15 MP" if dodge else f"Your move dealt {damage} damage"
        return {"finished":False,"text":f"{intro}. Enemy counterattack dealt {taken} damage.\n\n"+_battle_text(fresh,fighter["name"])}


def register(application, db: Database) -> None:
    """Register interactive handlers, replacing conflicting legacy command routes."""
    initialize(db)
    overridden={"explore","clan_leave"}
    for group, handlers in list(application.handlers.items()):
        application.handlers[group]=[h for h in handlers if not (isinstance(h,CommandHandler) and overridden.intersection(h.commands))]
    for name, handler in {"hunt":hunt,"explore":hunt,"dungeon":dungeon,"characters":character_menu,"character":character_menu,"clan_leave":clan_leave,"crown":crown,"upload":upload_art}.items():
        application.add_handler(CommandHandler(name,handler),group=0)
    application.add_handler(MessageHandler(filters.COMMAND,auto_register,block=False),group=-2)
    application.add_handler(CallbackQueryHandler(callbacks,pattern=r"^rpg:"),group=0)
