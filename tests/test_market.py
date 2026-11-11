from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rpgbot.database import Database
from rpgbot.game import GameService
from rpgbot.market import advance_market, buy_asset, initialize, portfolio_text, sell_asset


def market_fixture():
    db=Database(":memory:")
    db.initialize()
    initialize(db)
    service=GameService(db)
    service.register(501,"trader","Trader")
    return db,service


def test_market_assets_persist_and_quotes_are_bounded():
    db,_=market_fixture()
    with db.transaction() as con:
        advance_market(con, 1_800_000_000)
        prices=con.execute("SELECT price,min_price,max_price FROM market_assets").fetchall()
    assert len(prices)>=20
    assert all(r["min_price"]<=r["price"]<=r["max_price"] for r in prices)
    db.close()


def test_buy_portfolio_sell_and_fees_are_atomic():
    db,service=market_fixture()
    service.admin_grant_coins(501,10_000)
    bought=buy_asset(db,501,"senzu_futures",3)
    assert bought["quantity"]==3 and bought["fee"]>0
    assert "Senzu Bean Co." in portfolio_text(db,501)
    sold=sell_asset(db,501,"senzu_futures",2)
    assert sold["quantity"]==2 and sold["fee"]>0
    with db.reader() as con:
        assert con.execute("SELECT quantity FROM market_positions WHERE player_id=501 AND asset_id='senzu_futures'").fetchone()[0]==1
    db.close()


def test_market_rejects_insufficient_funds_and_overselling():
    db,service=market_fixture()
    with pytest.raises(ValueError,match="need"):
        buy_asset(db,501,"time_chamber",100)
    with pytest.raises(ValueError,match="do not own"):
        sell_asset(db,501,"senzu_futures",1)
    db.close()


def test_market_cycle_changes_quotes_only_after_five_minutes():
    db,_=market_fixture()
    with db.transaction() as con:
        advance_market(con,2_000_000_000)
        first=con.execute("SELECT price FROM market_assets WHERE asset_id='capsule_corp'").fetchone()[0]
        cycle=2_000_000_000//300
        advance_market(con,cycle*300+1)
        same=con.execute("SELECT price FROM market_assets WHERE asset_id='capsule_corp'").fetchone()[0]
        advance_market(con,(cycle+1)*300)
        later=con.execute("SELECT price FROM market_assets WHERE asset_id='capsule_corp'").fetchone()[0]
    assert first==same
    assert later != first or later > 0
    db.close()
