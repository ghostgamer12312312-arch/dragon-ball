# Dragon Ball RPG — Capsule Corp. Exchange

A small modular Python Telegram RPG starting point with async SQLite persistence and a Dragon Ball-themed player market. The exchange has 20 fictional assets, inline-button buy/sell flows, a portfolio, bounded price movement, stock, and transaction fees. Prices update on five-minute market cycles. This is fictional in-game trading; Zeni is not real money and profits are not guaranteed.

## Run

Python 3.11+ and a token from Telegram's @BotFather are required.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Set BOT_TOKEN in .env; never commit or share the token
python -m rpgbot.runner
```

Optional settings: `ADMIN_IDS` (comma-separated Telegram numeric IDs), `DATABASE_PATH` (default `data/game.sqlite3`), and `LOG_LEVEL`.

## Commands

- `/start` — register/update your fighter profile
- `/profile` — view level and Zeni balance
- `/market` — browse 20 Capsule Corp. Exchange assets and buy/sell from inline buttons
- `/portfolio` — view holdings, market value, cost basis, and unrealized P/L
- `/help` — command guide

Trading uses Zeni, charges a disclosed 1% fee, validates price, stock, funds and holdings, and writes balances/positions/transactions atomically. Market quotes move up or down deterministically per five-minute market cycle, remain bounded by each asset's published floor and ceiling, and stock refreshes daily. Market value and realized/unrealized returns can decline; this is game entertainment and not financial advice.

The repository is a developing RPG foundation, not a claim that every feature from other prototypes is implemented. Use original or licensed artwork only. Keep `.env` secret and run one polling process per bot token.

## Tests

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests
```
