# Architecture Notes

This file captures the project context and working agreements so future changes do not depend on chat history.

## Product Summary

`snow-vibe` is a small backend and Telegram bot for comparing ski resorts by near-term weather quality.

The current UX is:

- Telegram bot with two main actions:
  - `Показать курорты`
  - `Выбрать лучший курорт`
- Resort details are shown as a formatted forecast card with:
  - resort title
  - updated timestamp
  - one block per spot on the mountain
  - dates, temperature range, and precipitation wording

## Current Resorts

Configured resorts are stored in `src/snow_vibe/resorts.py`.

Current set:

- `bigwood`
- `sheregesh`
- `rosa-khutor`

Each resort stores:

- display name
- provider
- timezone
- base coordinates
- multiple `spots` for the same resort, usually base + peak

## Weather Provider Strategy

The preferred strategy is:

1. Use an official or stable upstream API whenever possible.
2. Avoid scraping resort HTML unless the resort exposes unique local data that is unavailable elsewhere.

Current provider choices:

- Forecast provider: `api.met.no`
- Geocoding helper: OpenStreetMap Nominatim

This was chosen because resort pages often embed third-party weather widgets rather than expose a stable first-party API.

## Forecast Formatting Rules

Telegram formatting is implemented in `src/snow_vibe/serialization.py`.

Current display rules:

- Show exact dates instead of "today / tomorrow / day after tomorrow".
- Focus on temperature and precipitation.
- If precipitation is `< 1 mm`, show `-`.
- If precipitation is `>= 1 mm` and the day warms above zero, show `дождь`.
- If precipitation is `>= 1 mm` and temperatures stay at or below zero, show precipitation in `мм`.

The base/peak split is intentional and should be preserved.

## Best Resort Logic

The current "best resort" logic is intentionally simple and lives in `src/snow_vibe/services.py`.

Heuristic:

- Reward days in the next 3 days where:
  - precipitation is `>= 1 mm`
  - `max_temp_c <= 0`
- Penalize days where:
  - precipitation is `>= 1 mm`
  - `max_temp_c > 0` (treated as rain)

UX rule:

- The `Выбрать лучший курорт` button should return the same forecast card format as a manual resort selection.
- The only difference is a short explanation line above the card saying why the resort was selected.

This is a product decision, not just a technical detail.

## Telegram Bot Behavior

Telegram bot logic lives in `src/snow_vibe/bot.py`.

Important behavior:

- The bot supports both long polling and webhook mode.
- Webhook mode is the intended deployment mode.
- The webhook endpoint is `/telegram/webhook`.
- Webhook requests are protected with `SNOW_VIBE_TELEGRAM_WEBHOOK_SECRET`.
- Admin UI lives at `/admin`.

Main menu:

- `Показать курорты`
- `Выбрать лучший курорт`

`Показать курорты`:

- shows a list of resorts via inline buttons
- clicking one returns the resort forecast card

`Выбрать лучший курорт`:

- picks the resort automatically using the scoring logic
- returns the same forecast card format as a manual resort click

## Storage and Cache

Current storage implementation lives in `src/snow_vibe/storage.py`.

Current tables:

- `resort_forecasts`
- `app_state`

Current cache policy:

- forecast data is cached per resort and local resort day
- repeated requests on the same day return cached data unless `force=True`

Current purpose of the database:

- avoid repeated upstream API calls
- keep Telegram bot state
- allow admin inspection and edits

## Admin UI

Admin UI is built with SQLAdmin and wired in:

- `src/snow_vibe/admin.py`
- `src/snow_vibe/api.py`

Current behavior:

- `/admin` is protected with username/password from env vars
- used mainly for viewing and editing `resort_forecasts` and `app_state`
- when Turso is enabled, the current SQLAdmin integration is intentionally disabled for now because it is still wired to the local SQLAlchemy/SQLite path

## Deployment Notes

### Vercel

The app currently runs on Vercel.

Important caveat:

- Vercel does not provide durable local disk for app data.
- `/tmp` can be used for temporary files only.

Current code contains Vercel-specific safeguards so the app can run if `SNOW_VIBE_DB_PATH` points to `/tmp/snow_vibe.db`.

This is acceptable for quick experiments, but not for durable long-term storage.

### Git / Vercel Setup

Current deployment path:

- source of truth is GitHub
- Vercel deploys from the repository
- webhook points directly to the Vercel domain

## Short-Term Technical Priorities

Most useful next steps:

1. Replace `/tmp` storage with a durable database.
2. Define the long-term schema instead of keeping only a raw forecast cache.
3. Improve best-resort scoring with more product nuance.
4. Decide whether to keep admin-only operations in SQLAdmin or move some of them into API endpoints.

## Working Rules

- Prefer stable upstream APIs over scraping.
- Preserve concise Telegram UX.
- Do not change the bot into a verbose analytical tool unless explicitly requested.
- Keep comments and docs practical and implementation-oriented.
