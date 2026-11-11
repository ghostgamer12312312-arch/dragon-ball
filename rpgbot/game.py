from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from . import market_service as market
from .database import Database
from .data_catalog import ALL_CHARACTERS, BANNERS, ITEMS, SKILLS


class GameError(ValueError):
    """Expected player-facing game-rule error."""


async def register_player(db: Database, user_id: int, username: str | None, name: str):
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute(
            "INSERT INTO players(telegram_id, username, display_name) VALUES(?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, display_name=excluded.display_name",
            (user_id, username, name),
        )
        await con.execute("INSERT OR IGNORE INTO owned_characters(player_id, character_id) VALUES(?, 'goku')", (user_id,))
        await con.commit()
        row = await (await con.execute("SELECT * FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        if row["banned"]:
            raise GameError("This account is restricted from game actions.")
        return dict(row)
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def profile(db: Database, user_id: int):
    con = await db.connect()
    try:
        row = await (await con.execute("SELECT * FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        if not row:
            raise GameError("Use /start to create your fighter profile.")
        if row["banned"]:
            raise GameError("This account is restricted from game actions.")
        return dict(row)
    finally:
        await con.close()


async def buy_asset(db, user_id, asset_id, quantity):
    return await market.buy_asset(db, user_id, asset_id, quantity)


async def sell_asset(db, user_id, asset_id, quantity):
    return await market.sell_asset(db, user_id, asset_id, quantity)


async def market_page(db, page=0):
    return await market.market_page(db, page)


async def portfolio(db, user_id):
    return await market.portfolio(db, user_id)


async def buy_shop_item(db: Database, user_id: int, item_id: str, quantity: int = 1):
    if quantity < 1:
        raise GameError("You must buy at least 1 item.")

    item = ITEMS.get(item_id)
    if item is None:
        raise GameError("Unknown shop item.")

    total = item["price"] * quantity
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        player = await (await con.execute("SELECT coins FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        if not player:
            raise GameError("Use /start before shopping.")
        if player["coins"] < total:
            raise GameError(f"You need {total:,} Zeni for this purchase.")

        await con.execute("UPDATE players SET coins = coins - ? WHERE telegram_id = ?", (total, user_id))
        await con.execute(
            "INSERT INTO owned_items(player_id, item_id, quantity) VALUES(?,?,?) ON CONFLICT(player_id,item_id) DO UPDATE SET quantity=quantity+excluded.quantity",
            (user_id, item_id, quantity),
        )
        await con.commit()
        return {"item_id": item_id, "name": item["name"], "quantity": quantity, "total": total}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def use_item(db: Database, user_id: int, item_id: str):
    item = ITEMS.get(item_id)
    if item is None:
        raise GameError("Unknown item.")

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        row = await (await con.execute("SELECT quantity FROM owned_items WHERE player_id=? AND item_id=?", (user_id, item_id))).fetchone()
        if not row or row["quantity"] <= 0:
            raise GameError("You do not own that item.")

        await con.execute("UPDATE owned_items SET quantity = quantity - 1 WHERE player_id=? AND item_id=?", (user_id, item_id))

        if item["effect"] == "energy":
            await con.execute("UPDATE players SET energy = min(max_energy, energy + ?) WHERE telegram_id=?", (item["amount"], user_id))
        elif item["effect"] == "xp":
            await con.execute("UPDATE players SET xp = xp + ? WHERE telegram_id=?", (item["amount"], user_id))
        elif item["effect"] == "coins":
            await con.execute("UPDATE players SET coins = coins + ? WHERE telegram_id=?", (item["amount"], user_id))
        elif item["effect"] == "stats":
            await con.execute("UPDATE players SET stat_points = stat_points + ? WHERE telegram_id=?", (item["amount"], user_id))

        await con.commit()
        return {"item_id": item_id, "name": item["name"], "effect": item["effect"], "amount": item["amount"]}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def learn_skill(db: Database, user_id: int, skill_id: str):
    skill = SKILLS.get(skill_id)
    if skill is None:
        raise GameError("Unknown skill.")

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        player = await (await con.execute("SELECT coins FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        if not player:
            raise GameError("Use /start before learning skills.")

        cost = max(30, skill["mp_cost"] * 4)
        if player["coins"] < cost:
            raise GameError(f"You need {cost:,} Zeni to learn {skill['name']}.")

        existing = await (await con.execute("SELECT 1 FROM owned_skills WHERE player_id=? AND skill_id=?", (user_id, skill_id))).fetchone()
        if existing:
            raise GameError("You already know this skill.")

        await con.execute("UPDATE players SET coins = coins - ? WHERE telegram_id=?", (cost, user_id))
        await con.execute("INSERT INTO owned_skills(player_id, skill_id, slot) VALUES(?,?,NULL)", (user_id, skill_id))
        await con.commit()
        return {"skill_id": skill_id, "name": skill["name"], "cost": cost}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def equip_skill(db: Database, user_id: int, skill_id: str, slot: int):
    if slot not in (1, 2, 3):
        raise GameError("Skill slots are 1, 2, or 3.")

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        row = await (await con.execute("SELECT 1 FROM owned_skills WHERE player_id=? AND skill_id=?", (user_id, skill_id))).fetchone()
        if not row:
            raise GameError("You do not own this skill.")
        await con.execute("UPDATE owned_skills SET slot = CASE WHEN skill_id=? THEN ? ELSE slot END WHERE player_id=?", (skill_id, slot, user_id))
        await con.commit()
        return {"skill_id": skill_id, "slot": slot}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def gacha_pull(db: Database, user_id: int, banner_id: str = "starter"):
    banner = BANNERS.get(banner_id)
    if banner is None:
        raise GameError("Unknown banner.")

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        player = await (await con.execute("SELECT coins FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        if not player:
            raise GameError("Use /start before pulling.")

        cost = banner["cost"]
        if player["coins"] < cost:
            raise GameError(f"You need {cost:,} Zeni to pull this banner.")

        await con.execute("UPDATE players SET coins = coins - ? WHERE telegram_id=?", (cost, user_id))

        pool = [c for c in ALL_CHARACTERS if c["rarity"] in (3, 4, 5)]
        if banner_id == "legend":
            pool = [c for c in ALL_CHARACTERS if c["rarity"] >= 4]
        elif banner_id == "mythic":
            pool = [c for c in ALL_CHARACTERS if c["rarity"] >= 5]

        hero = random.choices(pool, weights=[max(1, c["rarity"]) for c in pool], k=1)[0]

        existing = await (await con.execute("SELECT 1 FROM owned_characters WHERE player_id=? AND character_id=?", (user_id, hero["id"]))).fetchone()
        if existing:
            await con.execute("UPDATE players SET gems = gems + 10 WHERE telegram_id=?", (user_id,))
            await con.commit()
            return {"reward": hero["name"], "duplicate": True, "bonus_gems": 10}

        await con.execute(
            "INSERT INTO owned_characters(player_id, character_id, level, shards) VALUES(?,?,1,0) ON CONFLICT(player_id,character_id) DO UPDATE SET shards = shards + 1",
            (user_id, hero["id"]),
        )
        await con.commit()
        return {"reward": hero["name"], "duplicate": False, "banner": banner_id}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def start_battle(db: Database, user_id: int, kind: str = "hunt", enemy_name: str | None = None):
    from .data_catalog import ENEMIES

    await profile(db, user_id)
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        player = await (await con.execute("SELECT * FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        active = await (await con.execute("SELECT id FROM active_battles WHERE player_id=? AND status='active'", (user_id,))).fetchone()
        if active:
            row = await (await con.execute("SELECT * FROM active_battles WHERE id=?", (active["id"],))).fetchone()
            await con.commit()
            return dict(row)

        if player["energy"] < 10:
            raise GameError("You need 10 energy to start a battle.")

        enemy = next((e for e in ENEMIES if e["name"] == enemy_name), None) if enemy_name else random.choice(ENEMIES)
        player_max_hp = 100 + player["level"] * 10 + player["vit_stat"] * 3
        enemy_hp = enemy["hp"] + player["level"] * 7

        await con.execute("UPDATE players SET energy = energy - 10 WHERE telegram_id=?", (user_id,))
        cur = await con.execute(
            "INSERT INTO active_battles(player_id, kind, enemy, enemy_hp, enemy_max_hp, player_hp, player_max_hp, mp, ult, transformed, turn, status, created_at) VALUES(?,?,?,?,?,?,?,?,0,0,0,'active',strftime('%s','now'))",
            (user_id, kind, enemy["name"], enemy_hp, enemy_hp, player_max_hp, player_max_hp, 100),
        )
        row = await (await con.execute("SELECT * FROM active_battles WHERE id=?", (cur.lastrowid,))).fetchone()
        await con.commit()
        return dict(row)
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def battle_action(db: Database, user_id: int, battle_id: int, action: str):
    from .data_catalog import ENEMIES

    allowed = {"attack", "skill1", "skill2", "dodge", "transform", "switch", "flee"}
    if action not in allowed:
        raise GameError("Unknown battle action.")

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        battle = await (await con.execute("SELECT * FROM active_battles WHERE id=? AND player_id=? AND status='active'", (battle_id, user_id))).fetchone()
        if not battle:
            raise GameError("Battle is finished or does not belong to you.")

        player = await (await con.execute("SELECT * FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        if action == "flee":
            await con.execute("UPDATE active_battles SET status='fled' WHERE id=?", (battle_id,))
            await con.commit()
            return {"finished": True, "text": "You fled safely. No battle rewards were granted."}

        attack = 18 + player["level"] * 4 + player["str_stat"] * 2
        hp = battle["player_hp"]
        mp = battle["mp"]
        ult = battle["ult"]
        transformed = battle["transformed"]

        if action == "skill1":
            if mp < 20:
                raise GameError("Skill 1 costs 20 MP.")
            mp -= 20
            attack = int(attack * 1.7)
        elif action == "skill2":
            if mp < 35:
                raise GameError("Skill 2 costs 35 MP.")
            mp -= 35
            attack = int(attack * 2.15)
            hp = min(battle["player_max_hp"], hp + 12)
        elif action == "dodge":
            mp = min(100, mp + 15)
        elif action == "transform":
            if transformed:
                raise GameError("Transformation already used this battle.")
            transformed = 1
            attack = int(attack * 1.5)
            ult = min(100, ult + 20)
        elif action == "switch":
            mp = min(100, mp + 10)
            attack = int(attack * 0.7)

        enemy_hp = max(0, battle["enemy_hp"] - attack)
        if action != "dodge":
            ult = min(100, ult + 15)

        turn = battle["turn"] + 1
        if enemy_hp == 0:
            reward = 40 + int(player["level"] * 5)
            await con.execute("UPDATE players SET coins = coins + ?, xp = xp + 30, pve_wins = pve_wins + 1 WHERE telegram_id=?", (reward, user_id))
            await con.execute("UPDATE active_battles SET status='won', enemy_hp=0, player_hp=?, mp=?, ult=?, turn=? WHERE id=?", (hp, mp, ult, turn, battle_id))
            await con.commit()
            return {"finished": True, "text": f"🏆 Victory! Earned {reward} Zeni and 30 XP."}

        enemy = next((e for e in ENEMIES if e["name"] == battle["enemy"]), None) or ENEMIES[0]
        damage = 0 if action == "dodge" else max(1, int(enemy["attack"] * random.uniform(0.75, 1.2)))
        hp = max(0, hp - damage)

        if hp == 0:
            await con.execute("UPDATE active_battles SET status='lost', player_hp=0, enemy_hp=?, turn=? WHERE id=?", (enemy_hp, turn, battle_id))
            await con.commit()
            return {"finished": True, "text": "💫 Defeat. Recover and try again with /hunt."}

        await con.execute(
            "UPDATE active_battles SET player_hp=?, enemy_hp=?, mp=?, ult=?, transformed=?, turn=? WHERE id=?",
            (hp, enemy_hp, mp, ult, transformed, turn, battle_id),
        )
        await con.commit()
        return {
            "finished": False,
            "enemy": battle["enemy"],
            "enemy_hp": enemy_hp,
            "enemy_max_hp": battle["enemy_max_hp"],
            "player_hp": hp,
            "player_max_hp": battle["player_max_hp"],
            "mp": mp,
            "ult": ult,
            "turn": turn,
            "damage": damage,
            "dealt": attack,
        }
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def set_character(db: Database, user_id: int, char_id: str):
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        row = await (await con.execute("SELECT 1 FROM owned_characters WHERE player_id=? AND character_id=?", (user_id, char_id))).fetchone()
        if not row:
            raise GameError("You do not own this character.")
        await con.execute("UPDATE players SET active_character=? WHERE telegram_id=?", (char_id, user_id))
        await con.commit()
    finally:
        await con.close()


async def daily_reward(db: Database, user_id: int):
    today = datetime.now(UTC).date().isoformat()
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        player = await (await con.execute("SELECT * FROM players WHERE telegram_id=?", (user_id,))).fetchone()
        if not player:
            raise GameError("Use /start first.")
        if player["last_daily"] == today:
            raise GameError("Daily reward already claimed.")

        streak = player["daily_streak"] + 1 if player["last_daily"] == yesterday else 1
        coins = 100 + min(streak, 7) * 20
        await con.execute(
            "UPDATE players SET coins = coins + ?, energy = min(max_energy, energy + 25), last_daily = ?, daily_streak = ? WHERE telegram_id=?",
            (coins, today, streak, user_id),
        )
        await con.commit()
        return {"coins": coins, "streak": streak}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def clan_create(db: Database, user_id: int, clan_name: str):
    name = clan_name.strip()
    if len(name) < 3 or len(name) > 24:
        raise GameError("Clan names must be 3–24 characters long.")

    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        row = await (await con.execute("SELECT 1 FROM clan_members WHERE player_id=?", (user_id,))).fetchone()
        if row:
            raise GameError("You are already in a clan.")

        cur = await con.execute("INSERT INTO clans(name, leader_id, treasury, created_at) VALUES(?,?,0,strftime('%s','now'))", (name, user_id))
        clan_id = await (await con.execute("SELECT id FROM clans WHERE name=? AND leader_id=?", (name, user_id))).fetchone()
        await con.execute("INSERT INTO clan_members(player_id, clan_id, role, joined_at) VALUES(?,?, 'leader', strftime('%s','now'))", (user_id, clan_id["id"]))
        await con.commit()
        return {"clan_name": name, "clan_id": clan_id["id"]}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


async def clan_leave(db: Database, user_id: int):
    con = await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        row = await (await con.execute("SELECT c.name, cm.role, cm.clan_id FROM clan_members cm JOIN clans c ON c.id = cm.clan_id WHERE cm.player_id=?", (user_id,))).fetchone()
        if not row:
            raise GameError("You are not in a clan.")

        if row["role"] == "leader":
            await con.execute("DELETE FROM clan_members WHERE player_id=?", (user_id,))
            await con.execute("DELETE FROM clans WHERE id=?", (row["clan_id"],))
            await con.commit()
            return {"left": True, "clan_name": row["name"], "leader_disbanded": True}

        await con.execute("DELETE FROM clan_members WHERE player_id=?", (user_id,))
        await con.commit()
        return {"left": True, "clan_name": row["name"], "leader_disbanded": False}
    except Exception:
        await con.rollback(); raise
    finally:
        await con.close()


__all__ = [
    "GameError",
    "register_player",
    "profile",
    "buy_asset",
    "sell_asset",
    "market_page",
    "portfolio",
    "buy_shop_item",
    "use_item",
    "learn_skill",
    "equip_skill",
    "gacha_pull",
    "start_battle",
    "battle_action",
    "set_character",
    "daily_reward",
    "clan_create",
    "clan_leave",
]
