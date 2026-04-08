"""Tests for Garmin historical gap-backfill scheduling helpers."""

import os
import sys
from datetime import date
from pathlib import Path

import pytest

# Reason: dags/ is not a package, so we add it to sys.path for test imports.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dags"))

import garmin_backfill_schedule


class TestGarminGapBackfillInterval:
    """Tests for Garmin gap-backfill cadence configuration."""

    def test_expected_use_reads_configured_interval(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should read the configured Garmin gap-backfill interval.

        Args:
            monkeypatch (pytest.MonkeyPatch): Pytest patch helper.

        Returns:
            None
        """
        monkeypatch.setenv("GARMIN_GAP_BACKFILL_INTERVAL_DAYS", "21")

        result = garmin_backfill_schedule.get_garmin_gap_backfill_interval_days()

        assert result == 21

    def test_failure_case_non_positive_interval_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should reject non-positive Garmin gap-backfill intervals.

        Args:
            monkeypatch (pytest.MonkeyPatch): Pytest patch helper.

        Returns:
            None
        """
        monkeypatch.setenv("GARMIN_GAP_BACKFILL_INTERVAL_DAYS", "0")

        with pytest.raises(ValueError):
            garmin_backfill_schedule.get_garmin_gap_backfill_interval_days()


class TestGarminGapBackfillSchedule:
    """Tests for Garmin historical gap-backfill due checks."""

    def test_expected_use_first_run_is_due(self) -> None:
        """Should treat a missing prior run marker as due.

        Returns:
            None
        """
        result = garmin_backfill_schedule.should_run_garmin_gap_backfill(
            reference_date=date(2025, 1, 15),
            last_run_date=None,
            interval_days=14,
        )

        assert result is True

    def test_edge_case_recent_successful_run_is_not_due(self) -> None:
        """Should skip the historical gap pass when the interval has not elapsed.

        Returns:
            None
        """
        result = garmin_backfill_schedule.should_run_garmin_gap_backfill(
            reference_date=date(2025, 1, 15),
            last_run_date=date(2025, 1, 5),
            interval_days=14,
        )

        assert result is False

    def test_failure_case_future_last_run_date_raises(self) -> None:
        """Should reject invalid future last-run markers.

        Returns:
            None
        """
        with pytest.raises(ValueError):
            garmin_backfill_schedule.should_run_garmin_gap_backfill(
                reference_date=date(2025, 1, 15),
                last_run_date=date(2025, 1, 16),
                interval_days=14,
            )


class TestGarminGapBackfillStateIO:
    """Tests for Garmin historical gap-backfill state persistence."""

    def test_expected_use_persists_and_loads_last_run_date(self, tmp_path: Path) -> None:
        """Should persist the last successful gap-backfill date and load it back.

        Args:
            tmp_path (Path): Temporary file directory.

        Returns:
            None
        """
        output_path = tmp_path / "garmin_daily.csv"

        state_path = garmin_backfill_schedule.persist_garmin_gap_backfill_run_date(
            reference_date=date(2025, 1, 15),
            output_path=str(output_path),
        )
        result = garmin_backfill_schedule.load_garmin_gap_backfill_last_run_date(
            str(output_path)
        )

        assert Path(state_path).exists()
        assert result == date(2025, 1, 15)

    def test_edge_case_uses_explicit_state_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Should honor an explicit Garmin gap-backfill state path override.

        Args:
            monkeypatch (pytest.MonkeyPatch): Pytest patch helper.
            tmp_path (Path): Temporary file directory.

        Returns:
            None
        """
        output_path = tmp_path / "garmin_daily.csv"
        state_path = tmp_path / "custom_state.txt"
        monkeypatch.setenv("GARMIN_GAP_BACKFILL_STATE_PATH", str(state_path))

        garmin_backfill_schedule.persist_garmin_gap_backfill_run_date(
            reference_date=date(2025, 1, 15),
            output_path=str(output_path),
        )
        result = garmin_backfill_schedule.load_garmin_gap_backfill_last_run_date(
            str(output_path)
        )

        assert result == date(2025, 1, 15)
        assert state_path.exists()

    def test_failure_case_invalid_state_date_raises(self, tmp_path: Path) -> None:
        """Should reject malformed persisted Garmin gap-backfill dates.

        Args:
            tmp_path (Path): Temporary file directory.

        Returns:
            None
        """
        output_path = tmp_path / "garmin_daily.csv"
        state_path = Path(
            garmin_backfill_schedule.get_garmin_gap_backfill_state_path(str(output_path))
        )
        state_path.write_text("2025/01/15", encoding="utf-8")

        with pytest.raises(ValueError):
            garmin_backfill_schedule.load_garmin_gap_backfill_last_run_date(
                str(output_path)
            )
