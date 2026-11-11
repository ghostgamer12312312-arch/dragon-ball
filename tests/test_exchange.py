from __future__ import annotations

import asyncio
import unittest

from rpgbot.database import Database
from rpgbot.game import GameError,buy_asset,market_page,portfolio,register_player,sell_asset


class ExchangeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db=Database(":memory:")
        # Shared in-memory SQLite requires an anchor; the bot uses a file DB.
        self.db.path="file:exchange-test?mode=memory&cache=shared"
        self.db._anchor=await __import__('aiosqlite').connect(self.db.path,uri=True)
        await self.db.initialize()
        await register_player(self.db,77,"trader","Test Fighter")

    async def asyncTearDown(self):
        if self.db._anchor: await self.db._anchor.close()

    async def test_assets_and_prices_are_bounded(self):
        rows,page,pages=await market_page(self.db)
        self.assertEqual(page,0)
        self.assertGreaterEqual(pages,3)
        con=await self.db.connect()
        try:
            cur=await con.execute("SELECT price,min_price,max_price FROM market_assets")
            self.assertTrue(all(r['min_price']<=r['price']<=r['max_price'] for r in await cur.fetchall()))
        finally:await con.close()

    async def test_buy_sell_and_portfolio(self):
        con=await self.db.connect()
        await con.execute("UPDATE players SET coins=10000 WHERE telegram_id=77")
        await con.commit();await con.close()
        bought=await buy_asset(self.db,77,"senzu_futures",3)
        self.assertEqual(bought['quantity'],3)
        self.assertGreater(bought['fee'],0)
        self.assertIn("Senzu Bean Co.",await portfolio(self.db,77))
        sold=await sell_asset(self.db,77,"senzu_futures",2)
        self.assertEqual(sold['quantity'],2)
        self.assertIn("×1",await portfolio(self.db,77))

    async def test_reject_invalid_trade(self):
        with self.assertRaises(GameError):await buy_asset(self.db,77,"time_chamber",100)
        with self.assertRaises(GameError):await sell_asset(self.db,77,"senzu_futures",1)


if __name__=="__main__":
    unittest.main()
