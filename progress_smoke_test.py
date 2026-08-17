"""Validate local accounts and missing-aware progress in an isolated database."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import local_store


def sample_user_data(index: int = 0) -> dict:
    return {
        "age": 24,
        "gender": "Female",
        "daily_screen_time_hours": 8.5 - index * 0.02,
        "social_media_hours": 3.8 - index * 0.01,
        "gaming_hours": 1.0,
        "work_study_hours": 4.0,
        "sleep_hours": 6.7 + index * 0.01,
        "notifications_per_day": 150,
        "app_opens_per_day": 100,
        "weekend_screen_time": 10.8 - index * 0.02,
        "stress_level": "Medium",
        "academic_work_impact": "No",
    }


def sample_result(index: int = 0) -> dict:
    return {
        "classification": {
            "risk_class": 1,
            "calibrated_risk_score": 0.80 - index * 0.004,
            "wellness_status": "Needs attention",
        },
        "projected_weekend_screen_time": 10.2,
        "cluster": {"cluster_id": 1},
        "explanation": [],
    }


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        local_store.DATABASE_PATH = Path(temp_dir) / "account_progress_test.db"
        local_store.init_db()

        ok, _, user_id = local_store.create_user("ProgressTest", "SafePass_2026!")
        assert ok and user_id is not None
        assert local_store.authenticate_user("ProgressTest", "SafePass_2026!") is not None
        assert local_store.authenticate_user("ProgressTest", "wrong-password") is None

        ok, _, second_user_id = local_store.create_user("SecondUser", "SafePass_2026!")
        assert ok and second_user_id is not None

        # Create 60 calendar days but intentionally skip five dates.
        missing_offsets = {8, 17, 29, 41, 52}
        for index in range(60):
            if index in missing_offsets:
                continue
            snapshot_date = date.today() - timedelta(days=59 - index)
            local_store.save_demo_snapshot(
                user_id=user_id,
                profile_name="ProgressTest",
                snapshot_date=snapshot_date.isoformat(),
                user_data=sample_user_data(index),
                result=sample_result(index),
            )

        dashboard = local_store.get_progress_dashboard(
            user_id,
            "ProgressTest",
            days=90,
        )
        assert dashboard["total_records"] == 55
        assert dashboard["has_month_comparison"] is True
        assert len(dashboard["timeline"]) == 90
        assert len(dashboard["checkin_calendar"]) == 30
        assert dashboard["missing_30"] >= 1
        assert any(not day["recorded"] for day in dashboard["checkin_calendar"])
        assert any(day["risk"] is None for day in dashboard["timeline"])

        # Same-day updates remain one daily point.
        before = dashboard["total_records"]
        local_store.save_demo_snapshot(
            user_id=user_id,
            profile_name="ProgressTest",
            snapshot_date=date.today().isoformat(),
            user_data=sample_user_data(99),
            result=sample_result(99),
        )
        after = local_store.get_progress_dashboard(
            user_id,
            "ProgressTest",
            days=90,
        )["total_records"]
        assert before == after

        # Another account must not see this user's history.
        isolated = local_store.get_progress_dashboard(
            second_user_id,
            "SecondUser",
            days=90,
        )
        assert isolated["total_records"] == 0

    print("ACCOUNT + PROGRESS SMOKE TEST PASSED")
    print("Password hashing, user isolation, missing days, daily upsert, and 90-day tracking are valid.")


if __name__ == "__main__":
    main()
