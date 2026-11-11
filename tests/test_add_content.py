from __future__ import annotations

import asyncio
import unittest

from rpgbot.add_content import SCHEMAS, list_content, parse_values, save_content
from rpgbot.database import Database
from rpgbot.game import GameError


class AddContentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db=Database(":memory:")
        self.db.path="file:add-content-tests?mode=memory&cache=shared"
        import aiosqlite
        self.db._anchor=await aiosqlite.connect(self.db.path,uri=True)
        await self.db.initialize()
        from rpgbot.add_content import initialize_content
        await initialize_content(self.db)
        con=await self.db.connect()
        await con.execute("INSERT INTO players(telegram_id,display_name) VALUES(123,'Test')")
        await con.commit();await con.close()

    async def asyncTearDown(self):
        if self.db._anchor: await self.db._anchor.close()

    def test_parser_validates_types_and_values(self):
        key,payload=parse_values("item","senzu|Senzu Bean|Restore energy|40|energy|25")
        self.assertEqual(key,"senzu");self.assertEqual(payload["price"],40)
        with self.assertRaises(GameError):parse_values("item","bad|Name|desc|oops|energy|1")
        with self.assertRaises(GameError):parse_values("item","bad|Name|desc|-1|energy|1")
        with self.assertRaises(GameError):parse_values("unknown","x|y")
        key,payload=parse_values("custom","capsule|material|Capsule|A useful object|{\"rarity\":\"rare\"}")
        self.assertEqual(payload["data_json"],{"rarity":"rare"})

    async def test_admin_content_persists_and_can_be_updated(self):
        key,payload=parse_values("pet","fox|Fox Pup|Rare|+5% attack|120")
        await save_content(self.db,"pet",key,payload,123)
        rows=await list_content(self.db,"pet")
        self.assertEqual(rows[0]["content_id"],"fox")
        payload["price"]=140
        await save_content(self.db,"pet",key,payload,123)
        self.assertIn('140',(await list_content(self.db,"pet"))[0]["payload_json"])

    async def test_grants_are_transactional_and_audited(self):
        from rpgbot.add_content import _grant
        from unittest.mock import SimpleNamespace
        result=await _grant(SimpleNamespace(effective_user=SimpleNamespace(id=999)),self.db,"coins",["123","500"],999)
        self.assertIn("500",result)
        con=await self.db.connect()
        try:
            row=await (await con.execute("SELECT coins FROM players WHERE telegram_id=123")).fetchone()
            self.assertEqual(row["coins"],600)
            audit=await (await con.execute("SELECT action FROM audit_log ORDER BY id DESC LIMIT 1")).fetchone()
            self.assertEqual(audit["action"],"grant_coins")
        finally:await con.close()

    async def test_character_grant_accepts_id_without_numeric_parse_bug(self):
        from rpgbot.add_content import _grant
        from unittest.mock import SimpleNamespace
        await _grant(SimpleNamespace(effective_user=SimpleNamespace(id=999)),self.db,"character",["123","goku","1"],999)
        con=await self.db.connect()
        try:
            row=await (await con.execute("SELECT 1 FROM owned_characters WHERE player_id=123 AND character_id='goku'")).fetchone()
            self.assertIsNotNone(row)
        finally:await con.close()


if __name__=="__main__":unittest.main()
