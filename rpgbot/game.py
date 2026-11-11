from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from .catalog import CHARACTERS, ENEMIES, ITEMS, QUESTS, RARITY_WEIGHTS
from .database import Database


class GameError(ValueError):
    """A safe, expected game-rule error suitable for a player message."""


class GameService:
    def __init__(self, db: Database, *, rng: random.Random | None = None,
                 clock: Callable[[], datetime] | None = None, epoch: Callable[[], float] | None = None):
        self.db = db
        self.rng = rng or random.Random()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.epoch = epoch or time.time

    def today(self) -> str:
        return self.clock().astimezone(UTC).date().isoformat()

    def require(self, con, pid: int):
        row = con.execute("SELECT * FROM players WHERE telegram_id=?", (pid,)).fetchone()
        if row is None:
            raise GameError("Use /start first to create your fighter profile.")
        if row["banned"]:
            raise GameError("This account is restricted from game actions.")
        return row

    def register(self, pid: int, username: str | None, name: str):
        with self.db.transaction() as con:
            cur = con.execute("INSERT OR IGNORE INTO players(telegram_id,username,display_name) VALUES(?,?,?)",
                              (pid, username, (name or "Fighter")[:64]))
            player = con.execute("SELECT * FROM players WHERE telegram_id=?", (pid,)).fetchone()
            if player["banned"]:
                raise GameError("This account is restricted from game actions.")
            con.execute("UPDATE players SET username=?,display_name=? WHERE telegram_id=?",
                        (username, (name or "Fighter")[:64], pid))
            con.execute("INSERT OR IGNORE INTO fighters(player_id,fighter_id) VALUES(?, 'goku')", (pid,))
            return dict(player), cur.rowcount == 1

    @staticmethod
    def award_xp(con, pid: int, amount: int) -> int:
        row = con.execute("SELECT level,xp,max_energy,energy FROM players WHERE telegram_id=?", (pid,)).fetchone()
        xp, level = int(row["xp"]) + max(0, amount), int(row["level"])
        gained = 0
        while xp >= level * 100:
            xp -= level * 100
            level += 1
            gained += 1
        max_energy = int(row["max_energy"]) + gained * 5
        con.execute("UPDATE players SET level=?,xp=?,max_energy=?,energy=min(?,energy+?) WHERE telegram_id=?",
                    (level, xp, max_energy, max_energy, gained * 5, pid))
        return gained

    def progress(self, con, pid: int, action: str) -> None:
        day = self.today()
        for key, quest in QUESTS.items():
            if quest["action"] == action:
                con.execute("INSERT INTO quests(player_id,day,quest_id,progress) VALUES(?,?,?,1) "
                            "ON CONFLICT(player_id,day,quest_id) DO UPDATE SET progress=min(?,progress+1)",
                            (pid, day, key, quest["goal"]))

    def profile(self, pid: int):
        with self.db.reader() as con:
            p = self.require(con, pid)
            fighter = CHARACTERS.get(p["active_character"], CHARACTERS["goku"])
            count = con.execute("SELECT COUNT(*) FROM fighters WHERE player_id=?", (pid,)).fetchone()[0]
            return {**dict(p), "fighter": fighter, "collection_size": count}

    def explore(self, pid: int):
        with self.db.transaction() as con:
            p = self.require(con, pid)
            if p["energy"] < 10:
                raise GameError("You need 10 energy to explore. Use /rest or an energy item.")
            enemy = self.rng.choice(ENEMIES)
            char = CHARACTERS.get(p["active_character"], CHARACTERS["goku"])
            owned = con.execute("SELECT 1 FROM fighters WHERE player_id=? AND fighter_id=?", (pid,p["active_character"])).fetchone()
            if not owned:
                char = CHARACTERS["goku"]
            attack = char["attack"] + p["level"] * 3
            hp = char["hp"] + p["level"] * 4
            enemy_hp = enemy["hp"] + p["level"] * 6
            remaining, turns = hp, 0
            while remaining > 0 and enemy_hp > 0 and turns < 30:
                turns += 1
                enemy_hp -= max(1, int(attack * self.rng.uniform(.85,1.15)))
                if enemy_hp > 0:
                    remaining -= max(1, int((enemy["attack"] + p["level"] * 2) * self.rng.uniform(.85,1.15)))
            won = enemy_hp <= 0
            con.execute("UPDATE players SET energy=energy-10 WHERE telegram_id=?", (pid,))
            coins = self.rng.randint(*enemy["coins"]) if won else 0
            xp = self.rng.randint(*enemy["xp"]) if won else 5
            con.execute("UPDATE players SET coins=coins+? WHERE telegram_id=?", (coins,pid))
            levels = self.award_xp(con,pid,xp)
            if won:
                self.progress(con,pid,"explore")
                self.progress(con,pid,"battle")
            updated = con.execute("SELECT level,xp,energy,max_energy FROM players WHERE telegram_id=?",(pid,)).fetchone()
            return {"enemy":enemy["name"],"won":won,"hp_left":max(0,remaining),"coins":coins,"xp":xp,"levels":levels,**dict(updated)}

    def train(self,pid:int):
        with self.db.transaction() as con:
            p=self.require(con,pid)
            if p["energy"]<15: raise GameError("You need 15 energy to train.")
            xp=self.rng.randint(20,35)
            con.execute("UPDATE players SET energy=energy-15 WHERE telegram_id=?",(pid,))
            levels=self.award_xp(con,pid,xp); self.progress(con,pid,"train")
            return {"xp":xp,"levels":levels,**dict(con.execute("SELECT level,xp,energy,max_energy FROM players WHERE telegram_id=?",(pid,)).fetchone())}

    def rest(self,pid:int):
        with self.db.transaction() as con:
            p=self.require(con,pid)
            if p["energy"]>=p["max_energy"]: raise GameError("Your energy is already full.")
            if p["coins"]<25: raise GameError("Resting costs 25 coins.")
            con.execute("UPDATE players SET coins=coins-25,energy=max_energy WHERE telegram_id=?",(pid,))
            return dict(con.execute("SELECT energy,max_energy,coins FROM players WHERE telegram_id=?",(pid,)).fetchone())

    def daily(self,pid:int):
        today=self.today(); yesterday=(self.clock().astimezone(UTC).date()-timedelta(days=1)).isoformat()
        with self.db.transaction() as con:
            p=self.require(con,pid)
            if p["last_daily"]==today: raise GameError("Daily reward already claimed. Come back tomorrow.")
            streak=p["daily_streak"]+1 if p["last_daily"]==yesterday else 1
            coins=100+min(streak-1,7)*15
            con.execute("UPDATE players SET last_daily=?,daily_streak=?,coins=coins+?,energy=min(max_energy,energy+25) WHERE telegram_id=?",(today,streak,coins,pid))
            p=con.execute("SELECT energy,max_energy FROM players WHERE telegram_id=?",(pid,)).fetchone()
            return {"coins":coins,"streak":streak,**dict(p)}

    def quests(self,pid:int):
        with self.db.transaction() as con:
            self.require(con,pid); day=self.today()
            for key in QUESTS:
                con.execute("INSERT OR IGNORE INTO quests(player_id,day,quest_id) VALUES(?,?,?)",(pid,day,key))
            rows=con.execute("SELECT quest_id,progress,claimed FROM quests WHERE player_id=? AND day=?",(pid,day)).fetchall()
            return [{"id":r["quest_id"],**QUESTS[r["quest_id"]],"progress":r["progress"],"claimed":bool(r["claimed"])} for r in rows]

    def claim(self,pid:int,key:str):
        if key not in QUESTS: raise GameError("Unknown quest. Run /quests to see valid IDs.")
        with self.db.transaction() as con:
            self.require(con,pid); q=con.execute("SELECT progress,claimed FROM quests WHERE player_id=? AND day=? AND quest_id=?",(pid,self.today(),key)).fetchone()
            if not q or q["progress"]<QUESTS[key]["goal"]: raise GameError("That quest is not complete yet.")
            if q["claimed"]: raise GameError("That quest reward was already claimed.")
            con.execute("UPDATE quests SET claimed=1 WHERE player_id=? AND day=? AND quest_id=?",(pid,self.today(),key))
            reward=QUESTS[key]; con.execute("UPDATE players SET coins=coins+? WHERE telegram_id=?",(reward["coins"],pid))
            levels=self.award_xp(con,pid,reward["xp"])
            return {"coins":reward["coins"],"xp":reward["xp"],"levels":levels}

    def summon(self,pid:int):
        with self.db.transaction() as con:
            p=self.require(con,pid)
            if p["coins"]<80: raise GameError("A summon costs 80 coins.")
            rarities,weights=zip(*RARITY_WEIGHTS); rarity=self.rng.choices(rarities,weights=weights,k=1)[0]
            options=[k for k,v in CHARACTERS.items() if v["rarity"]==rarity]; fid=self.rng.choice(options)
            old=con.execute("SELECT 1 FROM fighters WHERE player_id=? AND fighter_id=?",(pid,fid)).fetchone()
            con.execute("UPDATE players SET coins=coins-80 WHERE telegram_id=?",(pid,))
            if old:
                con.execute("UPDATE fighters SET shards=shards+1 WHERE player_id=? AND fighter_id=?",(pid,fid))
                shards=con.execute("SELECT shards FROM fighters WHERE player_id=? AND fighter_id=?",(pid,fid)).fetchone()[0]
            else:
                con.execute("INSERT INTO fighters(player_id,fighter_id) VALUES(?,?)",(pid,fid)); shards=0
            return {"id":fid,**CHARACTERS[fid],"duplicate":bool(old),"shards":shards}

    def collection(self,pid:int):
        with self.db.reader() as con:
            self.require(con,pid)
            rows=con.execute("SELECT fighter_id,shards FROM fighters WHERE player_id=? ORDER BY fighter_id",(pid,)).fetchall()
            return [{"id":r["fighter_id"],**CHARACTERS[r["fighter_id"]],"shards":r["shards"]} for r in rows]

    def select(self,pid:int,fid:str):
        if fid not in CHARACTERS: raise GameError("Unknown fighter ID. Run /collection.")
        with self.db.transaction() as con:
            self.require(con,pid)
            if not con.execute("SELECT 1 FROM fighters WHERE player_id=? AND fighter_id=?",(pid,fid)).fetchone(): raise GameError("You do not own that fighter.")
            con.execute("UPDATE players SET active_character=? WHERE telegram_id=?",(fid,pid))
            return CHARACTERS[fid]

    def shop(self): return [{"id":k,**v} for k,v in ITEMS.items()]

    def buy(self,pid:int,item_id:str,qty:int=1):
        if item_id not in ITEMS: raise GameError("Unknown item. Run /shop.")
        if not 1<=qty<=99: raise GameError("Quantity must be between 1 and 99.")
        item=ITEMS[item_id]; cost=item["price"]*qty
        with self.db.transaction() as con:
            p=self.require(con,pid)
            if p["coins"]<cost: raise GameError(f"You need {cost} coins for this purchase.")
            con.execute("UPDATE players SET coins=coins-? WHERE telegram_id=?",(cost,pid))
            con.execute("INSERT INTO inventory(player_id,item_id,quantity) VALUES(?,?,?) ON CONFLICT(player_id,item_id) DO UPDATE SET quantity=quantity+excluded.quantity",(pid,item_id,qty))
        return {"name":item["name"],"quantity":qty,"cost":cost}

    def inventory(self,pid:int):
        with self.db.reader() as con:
            self.require(con,pid)
            rows=con.execute("SELECT item_id,quantity FROM inventory WHERE player_id=? AND quantity>0",(pid,)).fetchall()
            return [{"id":r["item_id"],**ITEMS[r["item_id"]],"quantity":r["quantity"]} for r in rows]

    def use(self,pid:int,item_id:str):
        if item_id not in ITEMS: raise GameError("Unknown item. Run /inventory.")
        item=ITEMS[item_id]
        with self.db.transaction() as con:
            p=self.require(con,pid); inv=con.execute("SELECT quantity FROM inventory WHERE player_id=? AND item_id=?",(pid,item_id)).fetchone()
            if not inv or inv["quantity"]<1: raise GameError("You do not own that item.")
            if item["effect"]=="energy" and p["energy"]>=p["max_energy"]: raise GameError("Energy is already full; item was not consumed.")
            con.execute("UPDATE inventory SET quantity=quantity-1 WHERE player_id=? AND item_id=?",(pid,item_id))
            if item["effect"]=="energy": con.execute("UPDATE players SET energy=min(max_energy,energy+?) WHERE telegram_id=?",(item["amount"],pid))
            else: self.award_xp(con,pid,item["amount"])
            return dict(con.execute("SELECT energy,max_energy,level,xp FROM players WHERE telegram_id=?",(pid,)).fetchone())|{"name":item["name"],"effect":item["effect"],"amount":item["amount"]}

    def leaderboard(self):
        with self.db.reader() as con:
            return [dict(r) for r in con.execute("SELECT display_name,level,xp,coins FROM players WHERE banned=0 ORDER BY level DESC,xp DESC,coins DESC LIMIT 10")]

    def create_clan(self,pid:int,name:str):
        name=" ".join(name.split())
        if not 3<=len(name)<=24 or not re.fullmatch(r"[\w -]+",name): raise GameError("Clan name must be 3–24 letters, numbers, spaces, _ or -.")
        with self.db.transaction() as con:
            self.require(con,pid)
            if con.execute("SELECT 1 FROM clan_members WHERE player_id=?",(pid,)).fetchone(): raise GameError("Leave your current clan first.")
            try: cur=con.execute("INSERT INTO clans(name,leader_id) VALUES(?,?)",(name,pid))
            except Exception as exc:
                if "UNIQUE" in str(exc).upper(): raise GameError("That clan name is already taken.") from None
                raise
            con.execute("INSERT INTO clan_members(player_id,clan_id,role) VALUES(?,?,'leader')",(pid,cur.lastrowid))
            return {"id":cur.lastrowid,"name":name}

    def clan_info(self,pid:int):
        with self.db.reader() as con:
            self.require(con,pid)
            member=con.execute("SELECT c.id,c.name,m.role FROM clan_members m JOIN clans c ON c.id=m.clan_id WHERE m.player_id=?",(pid,)).fetchone()
            if member:
                members=[dict(r) for r in con.execute("SELECT p.display_name,m.role FROM clan_members m JOIN players p ON p.telegram_id=m.player_id WHERE m.clan_id=? ORDER BY m.role,p.display_name",(member["id"],))]
                return {"clan":dict(member),"members":members,"clans":[]}
            clans=[dict(r) for r in con.execute("SELECT c.id,c.name,COUNT(m.player_id) AS members FROM clans c LEFT JOIN clan_members m ON m.clan_id=c.id GROUP BY c.id ORDER BY members DESC,c.name LIMIT 10")]
            return {"clan":None,"members":[],"clans":clans}

    def join_clan(self,pid:int,cid:int):
        with self.db.transaction() as con:
            self.require(con,pid)
            if con.execute("SELECT 1 FROM clan_members WHERE player_id=?",(pid,)).fetchone(): raise GameError("You are already in a clan.")
            c=con.execute("SELECT id,name FROM clans WHERE id=?",(cid,)).fetchone()
            if not c: raise GameError("Clan not found.")
            if con.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id=?",(cid,)).fetchone()[0]>=30: raise GameError("That clan is full.")
            con.execute("INSERT INTO clan_members(player_id,clan_id) VALUES(?,?)",(pid,cid)); return dict(c)

    def leave_clan(self,pid:int):
        with self.db.transaction() as con:
            self.require(con,pid); m=con.execute("SELECT role,clan_id FROM clan_members WHERE player_id=?",(pid,)).fetchone()
            if not m: raise GameError("You are not in a clan.")
            if m["role"]=="leader": raise GameError("Leaders must use /clan_disband.")
            con.execute("DELETE FROM clan_members WHERE player_id=?",(pid,))

    def disband_clan(self,pid:int):
        with self.db.transaction() as con:
            self.require(con,pid); c=con.execute("SELECT id,name FROM clans WHERE leader_id=?",(pid,)).fetchone()
            if not c: raise GameError("Only the clan leader can disband it.")
            con.execute("DELETE FROM clans WHERE id=?",(c["id"],)); return c["name"]

    def raid_status(self):
        with self.db.reader() as con:
            boss=dict(con.execute("SELECT * FROM raid WHERE id=1").fetchone())
            top=[dict(r) for r in con.execute("SELECT p.display_name,h.damage FROM raid_hits h JOIN players p ON p.telegram_id=h.player_id ORDER BY h.damage DESC LIMIT 5")]
            return {"boss":boss,"top":top}

    def raid_attack(self,pid:int):
        now=int(self.epoch())
        with self.db.transaction() as con:
            p=self.require(con,pid)
            if p["energy"]<10: raise GameError("You need 10 energy to attack the raid boss.")
            if now-p["last_raid_at"]<60: raise GameError(f"Raid cooldown: {60-(now-p['last_raid_at'])} seconds remaining.")
            char=CHARACTERS.get(p["active_character"],CHARACTERS["goku"]); damage=(char["attack"]+p["level"]*3)*self.rng.randint(2,4)
            boss=con.execute("SELECT * FROM raid WHERE id=1").fetchone(); hp=max(0,boss["hp"]-damage); defeated=hp==0
            con.execute("UPDATE players SET energy=energy-10,last_raid_at=? WHERE telegram_id=?",(now,pid))
            con.execute("INSERT INTO raid_hits(player_id,damage,hits) VALUES(?,?,1) ON CONFLICT(player_id) DO UPDATE SET damage=damage+excluded.damage,hits=hits+1",(pid,damage))
            if defeated:
                con.execute("UPDATE players SET coins=coins+250 WHERE telegram_id=?",(pid,))
                con.execute("UPDATE raid SET hp=max_hp,cycle=cycle+1 WHERE id=1")
                con.execute("DELETE FROM raid_hits")
            else: con.execute("UPDATE raid SET hp=? WHERE id=1",(hp,))
            return {"damage":damage,"hp":hp,"max_hp":boss["max_hp"],"defeated":defeated}

    def admin_ban(self,pid:int,banned:bool):
        with self.db.transaction() as con:
            if not con.execute("SELECT 1 FROM players WHERE telegram_id=?",(pid,)).fetchone(): raise GameError("Player profile not found.")
            con.execute("UPDATE players SET banned=? WHERE telegram_id=?",(int(banned),pid))
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
