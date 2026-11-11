from __future__ import annotations

import unittest
from rpgbot.add_content import list_content, parse_values, save_content, grant
from rpgbot.database import Database
from rpgbot.game import GameError

class AddContentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import aiosqlite
        self.db=Database(":memory:")
        self.db.path="file:add-content-tests?mode=memory&cache=shared"
        self.db._anchor=await aiosqlite.connect(self.db.path,uri=True)
        await self.db.initialize()
        con=await self.db.connect()
        await con.execute("INSERT INTO players(telegram_id,display_name) VALUES(123,'Test')")
        await con.commit();await con.close()

    async def asyncTearDown(self):
        if self.db._anchor: await self.db._anchor.close()

    def test_parser(self):
        key,payload=parse_values("item","senzu|Senzu Bean|Restore energy|40|energy|25")
        self.assertEqual(key,"senzu");self.assertEqual(payload["price"],40)
        with self.assertRaises(GameError):parse_values("item","senzu|Name|desc|oops|energy|1")
        with self.assertRaises(GameError):parse_values("item","senzu|Name|desc|-1|energy|1")
        with self.assertRaises(GameError):parse_values("custom","a|b|c|d|[]")

    async def test_persist_content_and_admin_grant(self):
        key,payload=parse_values("pet","fox|Fox Pup|Rare|+5% attack|120")
        await save_content(self.db,"pet",key,payload,999)
        self.assertEqual((await list_content(self.db,"pet"))[0]["content_id"],"fox")
        result=await grant(self.db,999,"coins",["123","500"])
        self.assertIn("500",result)
        con=await self.db.connect()
        try:
            row=await (await con.execute("SELECT coins FROM players WHERE telegram_id=123")).fetchone()
            self.assertEqual(row["coins"],600)
        finally:await con.close()

    async def test_character_grant_and_bounds(self):
        await grant(self.db,999,"character",["123","goku","1"])
        con=await self.db.connect()
        try:
            row=await (await con.execute("SELECT 1 FROM owned_characters WHERE player_id=123 AND character_id='goku'")).fetchone()
            self.assertIsNotNone(row)
        finally:await con.close()
        with self.assertRaises(GameError):await grant(self.db,999,"coins",["123","-1"])
        with self.assertRaises(GameError):await grant(self.db,999,"pet",["123","fox","999999"])

if __name__=="__main__":unittest.main()
