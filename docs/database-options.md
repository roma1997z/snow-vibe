# Database Options

This document describes practical storage options for `snow-vibe` now that `/tmp` on Vercel is no longer sufficient.

## Current Problem

The app currently works on Vercel with SQLite in `/tmp`, but this is only temporary storage.

That means:

- cache entries can disappear at any time
- Telegram bot state can disappear
- admin edits are not durable
- `/tmp` is not a real development or production database

So the next storage decision should optimize for:

- durability
- low complexity
- reasonable fit for Python + FastAPI
- reasonable fit for Vercel webhook deployment

## Option 1: Turso / libSQL

Official references:

- https://docs.turso.tech/sdk/python/quickstart
- https://docs.turso.tech/sdk/python/reference
- https://docs.turso.tech/sdk

Why it fits this project:

- closest mental model to SQLite
- Python support exists via `libsql`
- works well for small apps and hobby workloads
- easiest path if we want to stay conceptually close to the current schema

Pros:

- SQLite-like developer experience
- durable remote database
- low operational overhead
- likely the smallest migration from the current codebase
- possible future use of embedded replicas outside Vercel

Cons:

- new driver and slightly different tooling than plain sqlite3
- not as universal as Postgres if the project grows a lot

Migration complexity:

- low to medium

My practical opinion:

- this is the best fit if we want the smallest jump from the current implementation

## Option 2: Neon Postgres

Official references:

- https://neon.com/docs/get-started-with-neon/connect-neon
- https://neon.com/docs/guides/python

Why it fits this project:

- durable serverless Postgres
- natural fit for Vercel-style deployments
- standard SQL and common Python tooling

Pros:

- very standard stack
- easy to grow into relational features later
- works well with SQLAlchemy and future schema evolution
- better long-term flexibility than SQLite-like options

Cons:

- larger migration from current sqlite3 code
- slightly more setup and more database ceremony

Migration complexity:

- medium

My practical opinion:

- best choice if we already think this project will grow into a more serious backend with richer schema and analytics

## Option 3: Supabase Postgres

Official references:

- https://supabase.com/docs/guides/database/overview
- https://supabase.com/docs/guides/database

Why it fits this project:

- managed Postgres with admin tooling and backups
- easy visual table management

Pros:

- very convenient dashboard
- built-in SQL editor
- easy manual inspection of data
- good if we want a spreadsheet-like admin experience

Cons:

- more platform than we currently need
- includes auth/storage/realtime features we are not using yet
- migration size similar to other Postgres options

Migration complexity:

- medium

My practical opinion:

- good if the dashboard/admin experience is a priority
- probably more than we need right now for the simplest version

## Option 4: Stay on SQLite, Move Off Vercel

This means:

- deploy the app on a VPS
- keep SQLite on real disk
- run webhook + admin + API on the same machine

Pros:

- minimal code changes
- simplest persistence story technically
- cheapest migration effort

Cons:

- loses the convenience of Vercel
- requires server administration
- less aligned with the current deployment path we already set up

Migration complexity:

- very low

My practical opinion:

- this is actually the simplest path if we optimize for "ship fast" rather than "serverless convenience"

## Recommendation

If we keep Vercel:

- choose `Turso / libSQL`

Reason:

- it is the smallest conceptual leap from our current SQLite-based design
- it gives us durable storage quickly
- it keeps the code simpler than moving straight to a full Postgres migration

If we are open to moving off Vercel:

- keep SQLite and deploy on VPS

Reason:

- simplest engineering path
- no real data-model migration
- easier to reason about for a small Python backend

If we expect the product to grow significantly:

- choose `Neon Postgres`

Reason:

- best long-term flexibility
- most standard backend ecosystem

## What I Would Do Next

Practical recommendation for this project right now:

1. Keep the current Vercel webhook deployment for momentum.
2. Replace `/tmp` with `Turso / libSQL`.
3. Leave the external schema intentionally small at first.

Important implementation note:

- the current codebase can be switched to Turso for the application storage path
- the existing SQLAdmin page is still SQLite-oriented, so admin UI should be treated as temporarily unavailable in Turso mode until a dedicated Turso/Postgres-friendly admin path is added

Suggested first durable tables:

- `resort_forecasts`
- `app_state`
- optionally `resort_selection_logs`

## Schema Direction

The current database stores mostly a raw cached payload. That is fine for now.

A better next version would store:

- `resort_forecasts`
  - resort slug
  - cache date
  - fetched at
  - provider
  - normalized payload JSON
- `app_state`
  - telegram offset and other system state
- `best_resort_runs` (optional)
  - when scoring happened
  - which resort won
  - score summary

This lets us keep the implementation simple while still making the data durable.
