"""Tests for Garmin fetch cadence around historical gap backfill."""

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

# Reason: dags/ is not a package, so we add it to sys.path for test imports.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dags"))

import fetch_garmin
import garmin_backfill_schedule


class TestFetchGarminBackfillCadence:
    """Tests for daily Garmin sync with biweekly historical backfill."""

    def test_expected_use_due_backfill_adds_gap_dates_and_updates_state(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Should include detected gap dates when the historical pass is due.

        Args:
            monkeypatch (pytest.MonkeyPatch): Pytest patch helper.
            tmp_path (Path): Temporary output directory.

        Returns:
            None
        """
        output_path = tmp_path / "garmin_daily.csv"
        pd.DataFrame(
            {
                "Date": ["2025-01-09", "2025-01-10"],
                "garmin_steps": [1900, 2000],
            }
        ).to_csv(output_path, index=False)

        class FixedDate(date):
            """Fixed date helper for deterministic fetch windows."""

            @classmethod
            def today(cls) -> date:
                """Return the fixed current date.

                Returns:
                    date: Fixed sync end date.
                """
                return cls(2025, 1, 12)

        fetched_dates: list[str] = []
        monkeypatch.setattr(fetch_garmin, "date", FixedDate)
        monkeypatch.setattr(fetch_garmin, "load_garmin_client_from_tokens", lambda: object())
        monkeypatch.setenv("GARMIN_HISTORICAL_START_DATE", "2025-01-01")
        monkeypatch.setenv("GARMIN_SYNC_OVERLAP_DAYS", "2")
        monkeypatch.setenv("GARMIN_GAP_BACKFILL_INTERVAL_DAYS", "14")
        monkeypatch.delenv("GARMIN_FORCE_FULL_REFRESH", raising=False)
        monkeypatch.setattr(
            fetch_garmin,
            "build_date_range_from_bounds",
            lambda start_date, end_date: [
                "2025-01-08",
                "2025-01-09",
                "2025-01-10",
                "2025-01-11",
            ],
        )
        monkeypatch.setattr(
            fetch_garmin,
            "find_garmin_daily_gap_dates",
            lambda *_args, **_kwargs: ["2025-01-05"],
        )

        def _normalize_day(_client: object, date_str: str) -> dict[str, int | str]:
            """Capture fetched dates and return synthetic Garmin rows.

            Args:
                _client (object): Ignored fake Garmin client.
                date_str (str): Garmin date being normalized.

            Returns:
                dict[str, int | str]: Synthetic Garmin row.
            """
            fetched_dates.append(date_str)
            return {
                "Date": date_str,
                "garmin_steps": {
                    "2025-01-05": 1500,
                    "2025-01-08": 1800,
                    "2025-01-09": 1900,
                    "2025-01-10": 2000,
                    "2025-01-11": 2100,
                }[date_str],
            }

        monkeypatch.setattr(fetch_garmin, "normalize_garmin_day", _normalize_day)

        result = fetch_garmin.fetch_garmin_daily_data(output_path=str(output_path))
        written = pd.read_csv(result)
        last_run_date = garmin_backfill_schedule.load_garmin_gap_backfill_last_run_date(
            str(output_path)
        )

        assert fetched_dates == [
            "2025-01-05",
            "2025-01-08",
            "2025-01-09",
            "2025-01-10",
            "2025-01-11",
        ]
        assert list(written["Date"]) == [
            "2025-01-05",
            "2025-01-08",
            "2025-01-09",
            "2025-01-10",
            "2025-01-11",
        ]
        assert last_run_date == date(2025, 1, 11)

    def test_edge_case_recent_backfill_run_skips_gap_detection(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Should keep the daily overlap refresh but skip historical gap detection when not due.

        Args:
            monkeypatch (pytest.MonkeyPatch): Pytest patch helper.
            tmp_path (Path): Temporary output directory.

        Returns:
            None
        """
        output_path = tmp_path / "garmin_daily.csv"
        pd.DataFrame(
            {
                "Date": ["2025-01-09", "2025-01-10"],
                "garmin_steps": [1900, 2000],
            }
        ).to_csv(output_path, index=False)
        garmin_backfill_schedule.persist_garmin_gap_backfill_run_date(
            reference_date=date(2025, 1, 5),
            output_path=str(output_path),
        )

        class FixedDate(date):
            """Fixed date helper for deterministic fetch windows."""

            @classmethod
            def today(cls) -> date:
                """Return the fixed current date.

                Returns:
                    date: Fixed sync end date.
                """
                return cls(2025, 1, 12)

        fetched_dates: list[str] = []
        monkeypatch.setattr(fetch_garmin, "date", FixedDate)
        monkeypatch.setattr(fetch_garmin, "load_garmin_client_from_tokens", lambda: object())
        monkeypatch.setenv("GARMIN_HISTORICAL_START_DATE", "2025-01-01")
        monkeypatch.setenv("GARMIN_SYNC_OVERLAP_DAYS", "2")
        monkeypatch.setenv("GARMIN_GAP_BACKFILL_INTERVAL_DAYS", "14")
        monkeypatch.delenv("GARMIN_FORCE_FULL_REFRESH", raising=False)
        monkeypatch.setattr(
            fetch_garmin,
            "build_date_range_from_bounds",
            lambda start_date, end_date: [
                "2025-01-08",
                "2025-01-09",
                "2025-01-10",
                "2025-01-11",
            ],
        )

        def _fail_if_gap_detection_runs(*_args, **_kwargs) -> list[str]:
            """Fail the test if biweekly gap detection is invoked early.

            Returns:
                list[str]: Never returns because the call is unexpected.
            """
            raise AssertionError("Historical gap detection should not run when not due.")

        def _normalize_day(_client: object, date_str: str) -> dict[str, int | str]:
            """Capture fetched dates and return synthetic Garmin rows.

            Args:
                _client (object): Ignored fake Garmin client.
                date_str (str): Garmin date being normalized.

            Returns:
                dict[str, int | str]: Synthetic Garmin row.
            """
            fetched_dates.append(date_str)
            return {
                "Date": date_str,
                "garmin_steps": {
                    "2025-01-08": 1800,
                    "2025-01-09": 1900,
                    "2025-01-10": 2000,
                    "2025-01-11": 2100,
                }[date_str],
            }

        monkeypatch.setattr(fetch_garmin, "find_garmin_daily_gap_dates", _fail_if_gap_detection_runs)
        monkeypatch.setattr(fetch_garmin, "normalize_garmin_day", _normalize_day)

        result = fetch_garmin.fetch_garmin_daily_data(output_path=str(output_path))
        written = pd.read_csv(result)
        last_run_date = garmin_backfill_schedule.load_garmin_gap_backfill_last_run_date(
            str(output_path)
        )

        assert fetched_dates == [
            "2025-01-08",
            "2025-01-09",
            "2025-01-10",
            "2025-01-11",
        ]
        assert list(written["Date"]) == [
            "2025-01-08",
            "2025-01-09",
            "2025-01-10",
            "2025-01-11",
        ]
        assert last_run_date == date(2025, 1, 5)

    def test_failure_case_invalid_backfill_state_bubbles_up(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Should fail clearly when the persisted backfill marker is malformed.

        Args:
            monkeypatch (pytest.MonkeyPatch): Pytest patch helper.
            tmp_path (Path): Temporary output directory.

        Returns:
            None
        """
        output_path = tmp_path / "garmin_daily.csv"
        pd.DataFrame(
            {
                "Date": ["2025-01-09", "2025-01-10"],
                "garmin_steps": [1900, 2000],
            }
        ).to_csv(output_path, index=False)
        state_path = Path(
            garmin_backfill_schedule.get_garmin_gap_backfill_state_path(
                str(output_path)
            )
        )
        state_path.write_text("2025/01/05", encoding="utf-8")

        class FixedDate(date):
            """Fixed date helper for deterministic fetch windows."""

            @classmethod
            def today(cls) -> date:
                """Return the fixed current date.

                Returns:
                    date: Fixed sync end date.
                """
                return cls(2025, 1, 12)

        monkeypatch.setattr(fetch_garmin, "date", FixedDate)
        monkeypatch.setenv("GARMIN_HISTORICAL_START_DATE", "2025-01-01")
        monkeypatch.setenv("GARMIN_SYNC_OVERLAP_DAYS", "2")
        monkeypatch.setenv("GARMIN_GAP_BACKFILL_INTERVAL_DAYS", "14")
        monkeypatch.delenv("GARMIN_FORCE_FULL_REFRESH", raising=False)

        with pytest.raises(ValueError):
            fetch_garmin.fetch_garmin_daily_data(output_path=str(output_path))
