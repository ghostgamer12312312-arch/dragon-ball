# Dragon Realm — Dragon Ball-inspired Telegram RPG

A modular Python Telegram RPG with persistent SQLite progression, PvE battles, fighter collection and summons, energy, daily rewards, quests, shop and inventory, clans, world raids, leaderboards, admin moderation, and a Dragon Ball-themed player exchange. Interactive hunt/explore/dungeon battles require a player-selected move each turn. The project uses text-only original game data and is an unofficial fan project.

## Run

Python 3.11+ and a Telegram token from @BotFather are required.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env locally; never commit or share the token
python -m rpgbot.main
```

Set `BOT_TOKEN`. `ADMIN_IDS` is an optional comma-separated list of numeric Telegram IDs. `DATABASE_PATH` defaults to `data/game.sqlite3`. In Telegram send `/start`, then `/help`.

## Commands

Core: `/start`, `/help`, `/profile`, `/hunt`, `/explore`, `/dungeon`, `/train`, `/rest`, `/daily`, `/quests`, `/claim`, `/summon`, `/collection`, `/select`, `/characters`, `/character`, `/shop`, `/buy`, `/inventory`, `/use`, `/leaderboard`, `/clan`, `/clan_create`, `/clan_join`, `/clan_leave`, `/clan_disband`, `/raid`, `/raid_attack`, `/market`, `/portfolio`.

Admin: `/admin_stats`, `/ban`, `/unban`, `/crown [heroes|npcs|boss|summons|map]`, `/upload <name>` (reply to a photo). Configure admin Telegram IDs using `ADMIN_IDS`.

## Capsule Corp. Exchange

Use `/market` to browse 20 Dragon Ball-themed tradeable assets, tap an asset, and buy or sell units with inline buttons. `/portfolio` shows holdings, current value, purchase basis, and unrealized profit/loss. Prices change deterministically every five minutes, stay within catalog limits, and use a daily supply reset. Transactions use Zeni (the game's coin balance), charge a disclosed 1% fee, validate funds/holdings/supply, and update balances and positions atomically. Quotes can move up or down; returns are not guaranteed. This is fictional in-game trading only, not real-money financial advice or a real securities market.

## Interactive battles and clan safety

`/hunt`, `/explore`, and `/dungeon` create a persistent battle card with Attack, two MP-costing skills, Dodge, Transform, Switch, and Flee buttons. The enemy responds only after a player action; no auto-battle is used. Each player can have one active encounter. Battles cost 10 energy and grant documented rewards on victory. Clan members see confirmation before leaving; leaders must transfer leadership or confirm disbandment. Admins can inspect missing art and store Telegram photo file IDs using `/crown` and `/upload`.

## Data and development

SQLite creates the database and feature tables on startup. Back up the DB file while stopped or use SQLite's online backup API. Never delete player data to update the game. Keep `.env` private and run only one polling process per bot token.

```bash
pip install pytest
pytest -q
```

This is an expanded playable foundation, not a claim that every requested subsystem is implemented. Full PvP, gear stats/forge, auction listings, pets, wishes, five-series callback browsing, multi-floor dungeons, and clan treasury raid rewards remain future work and are not represented as working features. Artwork must be original or licensed.
# Dragon Ball RPG Bot

This project is a clean, modular Telegram RPG bot designed to run on Android Termux and similar Python environments.

## Requirements
- Python 3.11+
- Telegram bot token from @BotFather
- A Telegram numeric user ID for admin access
- Android Termux or a Linux/macOS shell

## Setup on Termux

```bash
pkg update
pkg install git python python-dev clang
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
python -m rpgbot.runner
```

Edit `.env` and replace:
- `BOT_TOKEN` with your real bot token
- `ADMIN_IDS` with your Telegram numeric ID

## Useful commands
- `/start`
- `/help`
- `/profile`
- `/characters`
- `/character Goku`
- `/team`
- `/shop`
- `/inventory`
- `/skills`
- `/learn`
- `/gacha`
- `/pull`
- `/hunt`
- `/explore`
- `/dungeon`
- `/market`
- `/portfolio`
- `/sell`
- `/clan`
- `/clan_create MyClan`
- `/clan_leave`
- `/use senzu`

## Notes
- Keep `.env` private. Never commit your bot token.
- "The bot is designed for fictional, in-game entertainment only."
- Database file is stored in `data/game.sqlite3` by default.
