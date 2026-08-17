"""Create clearly labeled synthetic longitudinal history for judge-demo recording.

This helper never trains or changes a model. It creates a local presentation-only
account, generates historical inputs, scores them with the saved models, and
stores them as daily snapshots. Several days are intentionally skipped so the
missing-data UI can also be demonstrated.
"""

from __future__ import annotations

from datetime import date, timedelta
import random

from local_store import authenticate_user, create_user, save_demo_snapshot
from wellness_engine import get_behavior_cluster, predict_user, predict_weekend_screen_time


USERNAME = "JudgeDemo"
PASSWORD = "DemoOnly_2026!"
DAYS = 60
RANDOM_SEED = 2026
SKIP_DAY_INDEXES = {12, 25, 39, 48}


def bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def build_day(day_index: int, rng: random.Random) -> dict:
    progress = day_index / max(DAYS - 1, 1)
    daily_screen = 9.2 - 2.0 * progress + rng.uniform(-0.35, 0.35)
    social = 4.5 - 1.5 * progress + rng.uniform(-0.25, 0.25)
    gaming = 1.25 - 0.25 * progress + rng.uniform(-0.15, 0.15)
    sleep = 6.3 + 0.8 * progress + rng.uniform(-0.18, 0.18)
    notifications = round(205 - 55 * progress + rng.uniform(-12, 12))
    app_opens = round(132 - 35 * progress + rng.uniform(-9, 9))
    weekend = 12.0 - 2.2 * progress + rng.uniform(-0.45, 0.45)

    return {
        "age": 22,
        "gender": "Female",
        "daily_screen_time_hours": round(bounded(daily_screen, 0, 16), 2),
        "social_media_hours": round(bounded(social, 0, 12), 2),
        "gaming_hours": round(bounded(gaming, 0, 12), 2),
        "work_study_hours": 4.2,
        "sleep_hours": round(bounded(sleep, 0, 14), 2),
        "notifications_per_day": int(bounded(notifications, 0, 500)),
        "app_opens_per_day": int(bounded(app_opens, 0, 400)),
        "weekend_screen_time": round(bounded(weekend, 0, 18), 2),
        "stress_level": "Medium",
        "academic_work_impact": "Yes" if day_index < 38 else "No",
    }


def get_or_create_demo_user() -> dict:
    user = authenticate_user(USERNAME, PASSWORD)
    if user:
        return user

    ok, message, user_id = create_user(USERNAME, PASSWORD)
    if not ok:
        raise RuntimeError(f"Could not create demo user: {message}")
    return {"id": int(user_id), "username": USERNAME}


def main() -> None:
    user = get_or_create_demo_user()
    rng = random.Random(RANDOM_SEED)
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=DAYS - 1)
    stored = 0

    for day_index in range(DAYS):
        if day_index in SKIP_DAY_INDEXES:
            continue

        snapshot_date = start_date + timedelta(days=day_index)
        user_data = build_day(day_index, rng)
        classification = predict_user(user_data)
        result = {
            "classification": classification,
            "projected_weekend_screen_time": predict_weekend_screen_time(user_data),
            "cluster": get_behavior_cluster(user_data),
            "explanation": [],
            "demo_history": True,
        }

        save_demo_snapshot(
            user_id=int(user["id"]),
            profile_name=USERNAME,
            snapshot_date=snapshot_date.isoformat(),
            user_data=user_data,
            result=result,
        )
        stored += 1

    print(f"Created {stored} synthetic demo days for local account: {USERNAME}")
    print(f"Demo password: {PASSWORD}")
    print("Skipped dates are intentional so the missing-day UI is visible.")
    print("Presentation/demo data only — not real user history.")


if __name__ == "__main__":
    main()
