from __future__ import annotations

import json
from pathlib import Path

from report_generator import generate_pdf_report
from wellness_engine import full_analysis


BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    """Run a local smoke test before uploading the competition project."""

    required_paths = [
        BASE_DIR / "app.py",
        BASE_DIR / "wellness_engine.py",
        BASE_DIR / "local_store.py",
        BASE_DIR / "report_generator.py",
        BASE_DIR / "train_models.py",
        BASE_DIR / "templates" / "index.html",
        BASE_DIR / "templates" / "auth.html",
        BASE_DIR / "static" / "style.css",
        BASE_DIR / "static" / "app.js",
        BASE_DIR / "models" / "digital_wellness_rf.joblib",
        BASE_DIR / "models" / "digital_wellness_isotonic.joblib",
        BASE_DIR / "models" / "weekend_screen_regressor.joblib",
        BASE_DIR / "models" / "behavior_kmeans.joblib",
        BASE_DIR / "models" / "decision_policy.json",
        BASE_DIR / "models" / "metrics.json",
    ]

    missing = [
        str(path.relative_to(BASE_DIR))
        for path in required_paths
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            f"Missing submission files: {missing}"
        )

    user_data = {
        "age": 31,
        "gender": "Female",
        "daily_screen_time_hours": 9.19,
        "social_media_hours": 3.05,
        "gaming_hours": 2.87,
        "work_study_hours": 5.34,
        "sleep_hours": 6.42,
        "notifications_per_day": 235,
        "app_opens_per_day": 100,
        "weekend_screen_time": 11.92,
        "stress_level": "High",
        "academic_work_impact": "No",
    }

    personalization = {
        "occupation": "Student",
        "available_time": "30 minutes",
        "goal": "Reduce social media",
        "activity_preference": "Physical",
        "peak_usage_time": "Evening",
        "social_media_reason": "Habit",
        "device_platform": "Android",
    }

    result = full_analysis(
        user_data,
        personalization,
    )

    report_path = (
        BASE_DIR
        / "reports"
        / "pre_submission_smoke_report.pdf"
    )

    generate_pdf_report(
        output_path=report_path,
        profile_name="Judge Demo",
        user_data=user_data,
        personalization=personalization,
        result=result,
        next_checkin="Demo check-in",
    )

    metrics = json.loads(
        (
            BASE_DIR
            / "models"
            / "metrics.json"
        ).read_text(encoding="utf-8")
    )

    print("\n=== PRE-SUBMISSION CHECK PASSED ===")
    print(
        "Status:",
        result["classification"]["wellness_status"],
    )
    print(
        "Raw RF score:",
        f"{result['classification']['raw_risk_score'] * 100:.1f}%",
    )
    print(
        "Calibrated Model Risk Score:",
        f"{result['classification']['calibrated_risk_score'] * 100:.1f}%",
    )
    print(
        "Weekend estimate:",
        f"{result['projected_weekend_screen_time']:.2f} hours",
    )
    print(
        "Behavior cluster:",
        result["cluster"]["cluster_id"],
    )
    print(
        "Focus tools:",
        ", ".join(
            tool["name"]
            for tool in result[
                "activity_replacements"
            ]["focus_tools"]
        ),
    )
    print(
        "Balanced Accuracy:",
        f"{metrics['classifier']['balanced_accuracy']:.4f}",
    )
    print(
        "PDF generated:",
        report_path,
    )


if __name__ == "__main__":
    main()
