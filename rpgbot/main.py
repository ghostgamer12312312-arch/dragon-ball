from __future__ import annotations

import logging

from .config import load_settings
from .database import Database
from .feature_modules import register_feature_modules
from .game import GameService
from .handlers import build_application


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
    register_feature_modules(application)
    logging.getLogger(__name__).info("Starting Telegram RPG bot polling")
    application.run_polling(allowed_updates=None, close_loop=True)


if __name__ == "__main__":
    main()
