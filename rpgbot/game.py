from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from . import market_service as market
from .database import Database


class GameError(ValueError):
    """Expected player-facing game-rule error."""


async def register_player(db: Database, user_id: int, username: str | None, name: str):
    con=await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        await con.execute("INSERT INTO players(telegram_id,username,display_name) VALUES(?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,display_name=excluded.display_name",(user_id,username,(name or "Fighter")[:64]))
        await con.execute("INSERT OR IGNORE INTO owned_characters(player_id,character_id) VALUES(?, 'goku')",(user_id,))
        await con.commit()
        cur=await con.execute("SELECT * FROM players WHERE telegram_id=?",(user_id,)); row=await cur.fetchone()
        if row['banned']: raise GameError("This account is restricted from game actions.")
        return dict(row)
    except Exception:
        await con.rollback(); raise
    finally: await con.close()


async def profile(db: Database,user_id: int):
    con=await db.connect()
    try:
        cur=await con.execute("SELECT * FROM players WHERE telegram_id=?",(user_id,)); row=await cur.fetchone()
        if not row: raise GameError("Use /start to create your fighter profile.")
        if row['banned']: raise GameError("This account is restricted from game actions.")
        return dict(row)
    finally: await con.close()


async def buy_asset(db,user_id,asset_id,quantity): return await market.buy_asset(db,user_id,asset_id,quantity)
async def sell_asset(db,user_id,asset_id,quantity): return await market.sell_asset(db,user_id,asset_id,quantity)
async def market_page(db,page=0): return await market.market_page(db,page)
async def portfolio(db,user_id): return await market.portfolio(db,user_id)


async def start_battle(db,user_id,kind="hunt",enemy_name=None):
    from .data_catalog import ENEMIES
    await profile(db,user_id)
    con=await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        cur=await con.execute("SELECT * FROM players WHERE telegram_id=?",(user_id,)); p=await cur.fetchone()
        cur=await con.execute("SELECT id FROM active_battles WHERE player_id=? AND status='active'",(user_id,)); active=await cur.fetchone()
        if active:
            cur=await con.execute("SELECT * FROM active_battles WHERE id=?",(active['id'],)); row=await cur.fetchone(); await con.commit(); return dict(row)
        if p['energy']<10: raise GameError("You need 10 energy to start a battle.")
        enemy=next((x for x in ENEMIES if x['name']==enemy_name),None) if enemy_name else None
        enemy=enemy or random.choice(ENEMIES)
        max_hp=100+p['level']*10+p['vit_stat']*3
        hp=enemy['hp']+p['level']*7
        await con.execute("UPDATE players SET energy=energy-10 WHERE telegram_id=?",(user_id,))
        cur=await con.execute("INSERT INTO active_battles(player_id,kind,enemy,enemy_hp,enemy_max_hp,player_hp,player_max_hp,created_at) VALUES(?,?,?,?,?,?,?,strftime('%s','now'))",(user_id,kind,enemy['name'],hp,hp,max_hp,max_hp))
        cur=await con.execute("SELECT * FROM active_battles WHERE id=?",(cur.lastrowid,)); row=await cur.fetchone(); await con.commit(); return dict(row)
    except Exception: await con.rollback(); raise
    finally: await con.close()


async def battle_action(db,user_id,battle_id,action):
    from .data_catalog import ENEMIES
    allowed={'attack','skill1','skill2','dodge','transform','switch','flee'}
    if action not in allowed: raise GameError("Unknown battle action.")
    con=await db.connect()
    try:
        await con.execute("BEGIN IMMEDIATE")
        cur=await con.execute("SELECT * FROM active_battles WHERE id=? AND player_id=? AND status='active'",(battle_id,user_id)); b=await cur.fetchone()
        if not b: raise GameError("Battle is finished or does not belong to you.")
        cur=await con.execute("SELECT * FROM players WHERE telegram_id=?",(user_id,)); p=await cur.fetchone()
        if action=='flee':
            await con.execute("UPDATE active_battles SET status='fled' WHERE id=?",(battle_id,)); await con.commit(); return {'finished':True,'text':'You fled safely. No battle rewards were granted.'}
        atk=18+p['level']*4+p['str_stat']*2; hp=b['player_hp']; mp=b['mp']; ult=b['ult']; trans=b['transformed']; dodge=action=='dodge'
        if action=='skill1':
            if mp<20: raise GameError('Skill 1 costs 20 MP.')
            mp-=20; atk=int(atk*1.7)
        elif action=='skill2':
            if mp<35: raise GameError('Skill 2 costs 35 MP.')
            mp-=35; atk=int(atk*2.15); hp=min(b['player_max_hp'],hp+12)
        elif dodge: mp=min(100,mp+15)
        elif action=='transform':
            if trans: raise GameError('Transformation already used this battle.')
            trans=1; atk=int(atk*1.5); ult=min(100,ult+20)
        elif action=='switch': mp=min(100,mp+10); atk=int(atk*.7)
        if not dodge: b_enemy=max(0,b['enemy_hp']-atk); ult=min(100,ult+15)
        else: b_enemy=b['enemy_hp']
        turn=b['turn']+1
        if b_enemy==0:
            reward=40+int(p['level']*5)
            await con.execute("UPDATE players SET coins=coins+?,xp=xp+30,pve_wins=pve_wins+1 WHERE telegram_id=?",(reward,user_id))
            await con.execute("UPDATE active_battles SET status='won',enemy_hp=0,player_hp=?,mp=?,ult=?,turn=? WHERE id=?",(hp,mp,ult,turn,battle_id))
            await con.commit(); return {'finished':True,'text':f"🏆 Victory! Earned {reward} Zeni and 30 XP."}
        enemy=next((e for e in ENEMIES if e['name']==b['enemy']),None); enemy_attack=enemy['attack'] if enemy else 12
        damage=0 if dodge else max(1,int(enemy_attack*random.uniform(.75,1.2)))
        hp=max(0,hp-damage)
        if hp==0:
            await con.execute("UPDATE active_battles SET status='lost',player_hp=0,enemy_hp=?,turn=? WHERE id=?",(b_enemy,turn,battle_id)); await con.commit()
            return {'finished':True,'text':'💫 Defeat. Recover and try again with /hunt.'}
        await con.execute("UPDATE active_battles SET player_hp=?,enemy_hp=?,mp=?,ult=?,transformed=?,turn=? WHERE id=?",(hp,b_enemy,mp,ult,trans,turn,battle_id))
        await con.commit()
        return {'finished':False,'enemy':b['enemy'],'enemy_hp':b_enemy,'enemy_max_hp':b['enemy_max_hp'],'player_hp':hp,'player_max_hp':b['player_max_hp'],'mp':mp,'ult':ult,'turn':turn,'damage':damage,'dealt':0 if dodge else atk}
    except Exception: await con.rollback(); raise
    finally: await con.close()


async def set_character(db,user_id,char_id):
    con=await db.connect()
    try:
        await con.execute('BEGIN IMMEDIATE')
        cur=await con.execute('SELECT 1 FROM owned_characters WHERE player_id=? AND character_id=?',(user_id,char_id))
        if not await cur.fetchone(): raise GameError('You do not own this character.')
        await con.execute('UPDATE players SET active_character=? WHERE telegram_id=?',(char_id,user_id)); await con.commit()
    except Exception: await con.rollback(); raise
    finally: await con.close()


async def daily_reward(db,user_id):
    today=datetime.now(UTC).date().isoformat(); yesterday=(datetime.now(UTC).date()-timedelta(days=1)).isoformat()
    con=await db.connect()
    try:
        await con.execute('BEGIN IMMEDIATE'); cur=await con.execute('SELECT * FROM players WHERE telegram_id=?',(user_id,)); p=await cur.fetchone()
        if not p: raise GameError('Use /start first.')
        if p['last_daily']==today: raise GameError('Daily reward already claimed.')
        streak=p['daily_streak']+1 if p['last_daily']==yesterday else 1; coins=100+min(streak,7)*20
        await con.execute('UPDATE players SET coins=coins+?,energy=min(max_energy,energy+25),last_daily=?,daily_streak=? WHERE telegram_id=?',(coins,today,streak,user_id)); await con.commit()
        return {'coins':coins,'streak':streak}
    except Exception: await con.rollback(); raise
    finally: await con.close()
