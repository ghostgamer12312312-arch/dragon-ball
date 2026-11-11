from __future__ import annotations

import logging

from .config import load_settings
from .database import Database
from .main import build_application


def main():
    settings=load_settings()
    logging.basicConfig(level=getattr(logging,settings.log_level,logging.INFO),format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db=Database(settings.database_path)
    import asyncio
    asyncio.run(db.initialize())
    logging.getLogger(__name__).info("Starting Dragon Ball RPG polling")
    build_application(settings,db).run_polling()

if __name__=="__main__":main()
