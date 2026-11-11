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
