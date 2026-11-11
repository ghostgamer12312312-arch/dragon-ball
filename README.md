# Dragon Realm — Dragon Ball-inspired Telegram RPG

A modular Python Telegram RPG with SQLite progression, PvE battles, fighter collection and summons, energy, daily rewards, quests, shop and inventory, clans, world raids, leaderboards, and admin moderation. Interactive hunt/explore/dungeon battles require a player-selected move each turn. The project uses text-only original game data and is an unofficial fan project.

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

Core: `/start`, `/help`, `/profile`, `/hunt`, `/explore`, `/dungeon`, `/train`, `/rest`, `/daily`, `/quests`, `/claim`, `/summon`, `/collection`, `/select`, `/characters`, `/character`, `/shop`, `/buy`, `/inventory`, `/use`, `/leaderboard`, `/clan`, `/clan_create`, `/clan_join`, `/clan_leave`, `/clan_disband`, `/raid`, `/raid_attack`.

Admin: `/admin_stats`, `/ban`, `/unban`, `/crown [heroes|npcs|boss|summons|map]`, `/upload <name>` (reply to a photo). Configure admin Telegram IDs using `ADMIN_IDS`.

## Interactive battles and clan safety

`/hunt`, `/explore`, and `/dungeon` create a persistent battle card with Attack, two MP-costing skills, Dodge, Transform, Switch, and Flee buttons. The enemy responds only after a player action; no auto-battle is used. Each player can have one active encounter. Battles cost 10 energy and grant documented rewards on victory. Clan members see a confirmation before leaving; leaders must transfer leadership or confirm disbandment. Admins can inspect missing art and store Telegram photo file IDs using `/crown` and `/upload`.

## Data and development

SQLite creates the database and feature tables on startup. Back up the DB file while stopped or use SQLite's online backup API. Never delete player data to update the game. Keep `.env` private and run only one polling process per bot token.

```bash
pip install pytest
pytest -q
```

This is an expanded playable foundation, not a claim that every requested subsystem is implemented. This branch adds the interactive battle loop, clan-leave confirmation/leadership flow, auto-registration on command, dynamic art checklist/upload, and tap-to-inspect/equip owned fighters. Equipment stats and forging, player marketplace, gacha banners/pity, pets, Dragon Ball wishes, full five-series catalog, true multi-floor dungeons, and PvP remain future work and are not advertised as implemented. Artwork must be original or licensed.
