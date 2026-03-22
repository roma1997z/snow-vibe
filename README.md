# snow-vibe

Python backend for collecting ski resort forecasts, caching them in SQLite, and serving data to a future Telegram bot.

## Quick start

Create a virtualenv and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy environment variables:

```bash
cp .env.example .env
```

Set admin credentials in `.env` before deployment:

```bash
SNOW_VIBE_ADMIN_USERNAME=admin
SNOW_VIBE_ADMIN_PASSWORD=change-me
SNOW_VIBE_ADMIN_SESSION_SECRET=replace-with-a-long-random-secret
```

Fetch a cached forecast for BigWood:

```bash
python3 -m snow_vibe.cli forecast bigwood --pretty
```

Force a refresh from the provider:

```bash
python3 -m snow_vibe.cli forecast bigwood --pretty --force
```

Resolve coordinates for a new resort:

```bash
python3 -m snow_vibe.cli geocode "BigWood Kirovsk"
```

Run the API:

```bash
uvicorn snow_vibe.api:app --reload
```

Open the database admin:

```bash
open http://127.0.0.1:8000/admin
```

Start long-polling Telegram bot:

```bash
python3 -m snow_vibe.cli bot-poll
```

Register a Telegram webhook:

```bash
python3 -m snow_vibe.cli set-webhook https://your-domain.example/telegram/webhook
python3 -m snow_vibe.cli webhook-info
```

## Notes

- Forecasts use the official `api.met.no` Locationforecast API.
- Geocoding uses OpenStreetMap Nominatim.
- Forecast responses are cached in SQLite for one local resort day by default.
- A built-in SQLAdmin interface is available at `/admin` for browsing and editing SQLite data.
- `/admin` is protected by username/password from `.env`.
- Telegram can work via either long polling or `/telegram/webhook`.
- Protect the webhook with `SNOW_VIBE_TELEGRAM_WEBHOOK_SECRET`.
- Requests must include a meaningful `User-Agent`. Override it with `SNOW_VIBE_USER_AGENT` if needed.
- The local bot token is read from `.env`.
