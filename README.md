# Dragon Ball RPG — Capsule Corp. Exchange

A modular Python Telegram RPG with async SQLite persistence and a Dragon Ball-themed player exchange. It includes a persistent catalog-addition/admin tool so authorized admins can add game content without editing code or executing arbitrary scripts.

## Run

Python 3.11+ and a token from Telegram's @BotFather are required.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Set BOT_TOKEN and your numeric Telegram ID in ADMIN_IDS. Never commit the token.
python -m rpgbot.runner
```

## Commands

- `/start`, `/help`, `/profile`
- `/market`, `/portfolio` — browse and trade 20 fictional Dragon Ball assets
- `/add` — admin-only game content manager. Tap a category, then use the shown schema.
- `/add list [type]` — list dynamic records stored in the database.
- `/add coins USER_ID AMOUNT`, `/add gems USER_ID AMOUNT`
- `/add item USER_ID ITEM_ID QUANTITY`
- `/add character USER_ID CHARACTER_ID`

Supported data categories: item, character, skill, enemy, pet, region, gear, recipe, banner, and title. Example: `/add item senzu|Senzu Bean|Restore energy|40|energy|40`. The command validates types and ranges, upserts records in SQLite, and writes grants to an audit log. Content is stored as data only; it is never evaluated as Python or SQL. Existing game catalogs are not automatically overridden by custom content unless a feature explicitly loads those records.

Market quotes update every five minutes within catalog bounds, stock refreshes daily, and buy/sell uses atomic transactions and a disclosed 1% fee. Trading is fictional in-game entertainment; value may rise or fall and profit is not guaranteed.

## Tests

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests
```

Keep `.env` private and run one polling process per bot token. Use original or licensed artwork only.
