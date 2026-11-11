from __future__ import annotations

import logging

from .advanced import register as register_advanced
from .config import load_settings
from .database import Database
from .game import GameService
from .handlers import build_application
from .market import register as register_market


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    database = Database(settings.database_path)
    database.initialize()
    game = GameService(database)
    application = build_application(settings, game)
    register_advanced(application, database)
    register_market(application, database)
    logging.getLogger(__name__).info("Starting Telegram RPG bot polling")
    application.run_polling(allowed_updates=None, close_loop=True)


if __name__ == "__main__":
    main()
