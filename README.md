# Dragon Realm — Dragon Ball-inspired Telegram RPG

A modular Python Telegram RPG with persistent SQLite player progression, PvE battles, fighter collection and summons, energy, daily rewards, quests, shop and inventory, clans, world raids, leaderboards, and admin moderation. It uses original text data only and is an unofficial fan project.

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

## Gameplay commands

`/profile`, `/explore`, `/train`, `/rest`, `/daily`, `/quests`, `/claim`, `/summon`, `/collection`, `/select`, `/shop`, `/buy`, `/inventory`, `/use`, `/leaderboard`, `/clan`, `/clan_create`, `/clan_join`, `/clan_leave`, `/clan_disband`, `/raid`, `/raid_attack`.

Admin commands: `/admin_stats`, `/ban`, `/unban`. Admin IDs must be configured in `ADMIN_IDS`.

## Data and safety

The database is created on first startup and stores player data persistently. Back up the database file with the bot stopped or use SQLite's online backup API. Never delete the database to update the game. Keep `.env` private, restrict access to the bot token, and run only one polling process for a token. SQLite transactions protect multi-step game operations. This is a playable foundation; review and test balance and deployment choices before inviting a large public player base.

## Development

```bash
pip install pytest
pytest -q
```

## Scope

This version implements a coherent playable core, not every feature listed in the source repositories. Advanced PvP, gear stat systems, fusion, dragon-ball wishes, seasonal events, clan vault/perks, richer raid rewards, and additional quest cycles are future work and are not represented as implemented commands.
