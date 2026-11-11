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
