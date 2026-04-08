# 2026-04-03 - Garmin Gap Backfill Cadence Configuration

## Summary

This update keeps the normal Garmin incremental sync on the daily DAG cadence while moving the bounded historical Garmin gap-backfill pass onto a persisted 14-day cadence by default. It also exposes that cadence as an environment variable so the interval can be changed without editing code, and updates the project configuration/docs to show how to set it.

## What Changed

### Biweekly historical Garmin gap-backfill scheduling

- Added `dags/garmin_backfill_schedule.py` to centralize Garmin historical gap-backfill cadence configuration, last-run marker loading, due-date checks, and atomic state persistence.
- Updated `dags/fetch_garmin.py` so the normal overlap-based daily Garmin refresh still runs on every daily DAG execution.
- Updated the same fetch path so bounded historical gap detection and backfill now run only when the configured cadence is due instead of on every daily sync.
- Persisted the last successful historical gap-backfill run date only after a successful due run so failed syncs do not incorrectly defer the next repair attempt.

### Configurable environment-driven cadence

- Added `GARMIN_GAP_BACKFILL_INTERVAL_DAYS` to `.env.example` with a documented default value of `14`.
- Updated `docker-compose.yaml` so `GARMIN_GAP_BACKFILL_INTERVAL_DAYS` is passed through to the Airflow services from `.env`.
- Updated `readme.md` to explain that:
  - the daily Garmin overlap refresh still runs every day,
  - the bounded historical repair pass uses `GARMIN_GAP_BACKFILL_INTERVAL_DAYS`, and
  - leaving the variable unset preserves the default 14-day cadence.
- Left `.env` untouched so the runtime value can be added manually after reviewing `.env.example`.

### Tests

- Added `tests/test_garmin_backfill_schedule.py` for cadence parsing, due/not-due evaluation, persisted state handling, and invalid-state failures.
- Added `tests/test_fetch_garmin_backfill_cadence.py` for daily-sync behavior when the historical backfill pass is due and when it is not due.
- Verified focused Garmin test coverage with:
  - `pytest tests/test_garmin_backfill_schedule.py tests/test_fetch_garmin_backfill_cadence.py tests/test_fetch_garmin.py tests/test_garmin_gap_backfill.py tests/test_garmin_sync_storage.py -q`

## Operational Notes

- If `GARMIN_GAP_BACKFILL_INTERVAL_DAYS` is omitted, the bounded historical Garmin gap-backfill pass defaults to every 14 days.
- If you want a different cadence, set `GARMIN_GAP_BACKFILL_INTERVAL_DAYS` in `.env` and restart the relevant Airflow services so the updated environment is loaded.
- This change does not alter the daily DAG schedule or the normal recent-day Garmin overlap refresh behavior.
