"""Helpers for scheduling the bounded Garmin historical gap-backfill pass."""

from __future__ import annotations

import os
import tempfile
from datetime import date
from typing import Optional


DEFAULT_GARMIN_GAP_BACKFILL_INTERVAL_DAYS = 14
DEFAULT_GARMIN_GAP_BACKFILL_STATE_FILENAME = "garmin_gap_backfill_last_run.txt"


def get_garmin_gap_backfill_interval_days() -> int:
    """Resolve the Garmin historical gap-backfill interval.

    Returns:
        int: Positive number of days between historical gap-backfill passes.

    Raises:
        ValueError: If the configured interval is not a positive integer.
    """
    raw_value = os.getenv(
        "GARMIN_GAP_BACKFILL_INTERVAL_DAYS",
        str(DEFAULT_GARMIN_GAP_BACKFILL_INTERVAL_DAYS),
    )
    interval_days = int(raw_value)
    if interval_days <= 0:
        raise ValueError(
            "`GARMIN_GAP_BACKFILL_INTERVAL_DAYS` must be a positive integer."
        )
    return interval_days


def get_garmin_gap_backfill_state_path(output_path: str) -> str:
    """Resolve the persisted Garmin gap-backfill state path.

    Args:
        output_path (str): Primary Garmin daily CSV path.

    Returns:
        str: Filesystem path for the last-run marker.
    """
    configured_path = os.getenv("GARMIN_GAP_BACKFILL_STATE_PATH", "").strip()
    if configured_path:
        return configured_path
    output_dir = os.path.dirname(output_path) or "."
    return os.path.join(output_dir, DEFAULT_GARMIN_GAP_BACKFILL_STATE_FILENAME)


def load_garmin_gap_backfill_last_run_date(output_path: str) -> Optional[date]:
    """Load the last successful Garmin historical gap-backfill date.

    Args:
        output_path (str): Primary Garmin daily CSV path.

    Returns:
        Optional[date]: Persisted last-run date, if available.

    Raises:
        ValueError: If the stored date is not a valid ISO date.
    """
    state_path = get_garmin_gap_backfill_state_path(output_path)
    if not os.path.exists(state_path):
        return None
    with open(state_path, encoding="utf-8") as state_file:
        raw_value = state_file.read().strip()
    if raw_value == "":
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError(
            "Garmin gap-backfill state must contain a valid ISO date (YYYY-MM-DD)."
        ) from exc


def should_run_garmin_gap_backfill(
    reference_date: date,
    last_run_date: Optional[date],
    interval_days: Optional[int] = None,
) -> bool:
    """Return whether the Garmin historical gap-backfill pass is due.

    Args:
        reference_date (date): Date of the current completed Garmin sync window.
        last_run_date (Optional[date]): Last successful historical gap-backfill date.
        interval_days (Optional[int]): Optional cadence override in days.

    Returns:
        bool: True when the historical gap-backfill pass should run.

    Raises:
        ValueError: If the interval is invalid or the last-run date is in the future.
    """
    resolved_interval_days = (
        interval_days
        if interval_days is not None
        else get_garmin_gap_backfill_interval_days()
    )
    if resolved_interval_days <= 0:
        raise ValueError("`interval_days` must be a positive integer.")
    if last_run_date is None:
        return True
    if last_run_date > reference_date:
        raise ValueError(
            "Garmin gap-backfill last-run date cannot be later than the reference date."
        )
    return (reference_date - last_run_date).days >= resolved_interval_days


def persist_garmin_gap_backfill_run_date(reference_date: date, output_path: str) -> str:
    """Persist the last successful Garmin historical gap-backfill date atomically.

    Args:
        reference_date (date): Date of the completed Garmin sync window.
        output_path (str): Primary Garmin daily CSV path.

    Returns:
        str: Filesystem path that was updated.
    """
    state_path = get_garmin_gap_backfill_state_path(output_path)
    parent_dir = os.path.dirname(state_path) or "."
    os.makedirs(parent_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".txt",
        prefix=".garmin_gap_backfill_",
        dir=parent_dir,
        delete=False,
    ) as temp_file:
        temp_path = temp_file.name
        temp_file.write(reference_date.isoformat())
    try:
        os.replace(temp_path, state_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    return state_path
