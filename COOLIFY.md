# Coolify Deployment

Use a Git-backed `Docker Compose` application in Coolify and point it at `docker-compose.coolify.yml`.

## Recommended setup

1. Push this repository to a Git provider Coolify can read.
2. In Coolify, create a new `Application`.
3. Select the repository and choose the `Docker Compose` build pack.
4. Use `docker-compose.coolify.yml` from the repository root.
5. Expose only the `web` service publicly through Coolify. Keep `api`, `postgres`, and `redis` internal.
6. Add environment variables from `.env.example` in Coolify, especially:
   - `JOBSCOUT_DATABASE_URL=postgresql+psycopg://jobscout:jobscout@postgres:5432/jobscout`
   - `JOBSCOUT_REDIS_URL=redis://redis:6379/0`
   - any `JOBSCOUT_IMAP_*`, Discord, or SMTP secrets you actually use

## Notes

- The web container now runs a production Next.js build and talks to the API over the internal Docker network with `API_BASE_URL=http://api:8000`.
- The API runs Alembic migrations on container start.
- Postgres data persists in the `postgres_data` volume defined in Compose.
- `docker-compose.coolify.yml` intentionally omits published host ports so Coolify can route traffic without colliding with ports already in use on the server.
- Keep `docker-compose.yml` for direct local Docker usage outside Coolify.

## Verify after deploy

- Open the Coolify URL for `web`
- Confirm `/` loads the dashboard
- Confirm `/ops` loads the ops console
- Trigger one scheduler run and verify the worker logs show a completed cycle
