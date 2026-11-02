# Unused Alembic tree

Alembic is configured in `apps/api/alembic.ini` with `script_location = migrations`.

The files previously stored under `alembic/versions/` used revision IDs that collided
with the live `migrations/versions/` chain (`0010`–`0017`) and were never applied.

Those changes are recovered as `0050`–`0057` in `migrations/versions/`.
