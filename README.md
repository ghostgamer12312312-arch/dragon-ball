# Dragon Ball RPG — Capsule Corp. Exchange

A modular Python Telegram RPG with async SQLite persistence and a Dragon Ball-themed player exchange. Admins can safely expand the game catalog and grant player resources through `/add`.

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
- `/market`, `/portfolio` — browse and trade fictional Dragon Ball-themed assets
- `/add` — admin-only game manager with tap-to-select content categories
- `/add list [type]` — list persisted admin-created data
- `/add coins|gems|energy|xp|level USER_ID AMOUNT` — bounded admin grants
- `/add item|gear|character|skill|pet USER_ID CONTENT_ID QUANTITY` — grant owned game assets
- `/add dragonball USER_ID STAR QUANTITY` — grant Dragon Balls (star 1–7)

Supported persistent content types: `item`, `character`, `skill`, `enemy`, `pet`, `region`, `gear`, `recipe`, `banner`, `title`, `boss`, `quest`, `dungeon`, `market_asset`, and `custom`. `/add` validates fields, uses allowlisted schemas, performs grants in database transactions, and audits admin changes. Custom content is stored as JSON data; it is never interpreted as Python, SQL, or executable code. Dynamic records are safely stored and listable, but do not automatically alter hard-coded combat or market behavior unless a later game feature explicitly loads that record type.

Examples:

```text
/add coins 123456789 5000
/add character 123456789 goku 1
/add dragonball 123456789 4 1
/add item senzu|Senzu Bean|Restores energy|40|energy|40
/add custom capsule|material|Capsule|A useful item|{"rarity":"rare"}
```

Market quotes update every five minutes within catalog bounds, stock refreshes daily, and buy/sell uses atomic transactions and a disclosed 1% fee. Trading is fictional in-game entertainment; value can rise or fall.

## Tests

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests
```

Keep `.env` private and run one polling process per bot token. Use original or licensed artwork only.
