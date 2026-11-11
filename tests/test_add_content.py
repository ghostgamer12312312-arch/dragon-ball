from __future__ import annotations

import asyncio
import unittest

from rpgbot.add_content import SCHEMAS, list_content, parse_values, save_content
from rpgbot.database import Database


class AddContentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db=Database(":memory:")
        self.db.path="file:add-content-tests?mode=memory&cache=shared"
        import aiosqlite
        self.db._anchor=await aiosqlite.connect(self.db.path,uri=True)
        await self.db.initialize()
        from rpgbot.add_content import initialize_content
        await initialize_content(self.db)

    async def asyncTearDown(self):
        if self.db._anchor: await self.db._anchor.close()

    def test_parser_validates_types_and_values(self):
        key,payload=parse_values("item","senzu|Senzu Bean|Restore energy|40|energy|25")
        self.assertEqual(key,"senzu")
        self.assertEqual(payload["price"],40)
        with self.assertRaises(ValueError): parse_values("item","bad|Name|desc|oops|energy|1")
        with self.assertRaises(ValueError): parse_values("item","bad|Name|desc|-1|energy|1")
        with self.assertRaises(ValueError): parse_values("unknown","x|y")

    async def test_admin_content_persists_and_can_be_updated(self):
        key,payload=parse_values("pet","fox|Fox Pup|Rare|+5% attack|120")
        await save_content(self.db,"pet",key,payload,123)
        rows=await list_content(self.db,"pet")
        self.assertEqual(rows[0]["content_id"],"fox")
        payload["price"]=140
        await save_content(self.db,"pet",key,payload,123)
        rows=await list_content(self.db,"pet")
        self.assertIn('140',rows[0]["payload_json"])


if __name__=="__main__": unittest.main()
