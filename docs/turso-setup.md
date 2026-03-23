# Turso Setup

This is the shortest path to connect `snow-vibe` to Turso.

## 1. Install Turso CLI

Official docs:

- https://docs.turso.tech/cli/introduction

## 2. Login

```bash
turso auth login
```

## 3. Create a database

Pick a name, for example:

```bash
turso db create snow-vibe
```

## 4. Get the database URL

```bash
turso db show --url snow-vibe
```

It should look like:

```bash
libsql://snow-vibe-your-org.turso.io
```

## 5. Create an auth token

```bash
turso db tokens create snow-vibe
```

## 6. Put both values into `.env`

```bash
TURSO_DATABASE_URL=libsql://snow-vibe-your-org.turso.io
TURSO_AUTH_TOKEN=replace-me
```

If your existing environment already uses this name, the code now accepts it too:

```bash
TURSO_DATABASE_TURSO_AUTH_TOKEN=replace-me
```

## 7. Add the same variables to Vercel

Environment Variables:

- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`

## 8. Redeploy Vercel

Once the variables are set, redeploy the app.

## Notes

- When Turso is enabled, the app storage switches from local SQLite to Turso automatically.
- The current SQLAdmin page is still SQLite-oriented, so `/admin` should be considered temporarily unavailable in Turso mode.
