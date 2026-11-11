from __future__ import annotations

from rpgbot.advanced import battle_action, initialize, save_art, transfer_leader
from rpgbot.game import GameError


def test_interactive_battle_requires_manual_action_and_resolves(game):
    service, _, _ = game
    service.register(101, "fighter", "Fighter")
    initialize(service.db)
    with service.db.transaction() as con:
        con.execute("INSERT INTO active_battles(player_id,kind,enemy,enemy_hp,enemy_max_hp,player_hp,player_max_hp,created_at) VALUES(?,?,?,?,?,?,?,?)", (101,"hunt","Saibaman",1,1,100,100,1))
        battle_id=con.execute("SELECT last_insert_rowid()").fetchone()[0]
    result=battle_action(service.db,101,battle_id,"attack")
    assert result["finished"] is True
    assert "Victory" in result["text"]
    with __import__("pytest").raises(GameError, match="no longer active"):
        battle_action(service.db,101,battle_id,"attack")


def test_battle_actions_are_player_owned(game):
    service, _, _ = game
    service.register(101,"a","A")
    service.register(202,"b","B")
    initialize(service.db)
    with service.db.transaction() as con:
        con.execute("INSERT INTO active_battles(player_id,kind,enemy,enemy_hp,enemy_max_hp,player_hp,player_max_hp,created_at) VALUES(?,?,?,?,?,?,?,?)", (101,"hunt","Saibaman",50,50,100,100,1))
        bid=con.execute("SELECT last_insert_rowid()").fetchone()[0]
    with __import__("pytest").raises(GameError, match="no longer active"):
        battle_action(service.db,202,bid,"attack")


def test_art_upload_upsert_and_leader_transfer(game):
    service, _, _ = game
    service.register(101,"leader","Leader")
    service.register(202,"member","Member")
    initialize(service.db)
    save_art(service.db,"goku","telegram-file-id",101)
    from rpgbot.advanced import get_art
    assert get_art(service.db,"goku")=="telegram-file-id"
    clan=service.create_clan(101,"Warriors")
    service.join_clan(202,clan["id"])
    transfer_leader(service.db,101,202)
    with service.db.reader() as con:
        assert con.execute("SELECT role FROM clan_members WHERE player_id=202").fetchone()[0]=="leader"
        assert con.execute("SELECT role FROM clan_members WHERE player_id=101").fetchone()[0]=="officer"
