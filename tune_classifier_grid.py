from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "usage_data(2).csv"
OUTPUT_PATH = BASE_DIR / "models" / "grid_search_results.json"

FEATURES = [
    "age",
    "gender",
    "daily_screen_time_hours",
    "social_media_hours",
    "gaming_hours",
    "work_study_hours",
    "sleep_hours",
    "notifications_per_day",
    "app_opens_per_day",
    "weekend_screen_time",
    "stress_level",
    "academic_work_impact",
]

CATEGORICAL = [
    "gender",
    "stress_level",
    "academic_work_impact",
]


def main() -> None:
    """Run a small, reproducible GridSearchCV verification experiment."""

    df = pd.read_csv(DATA_PATH)
    X = df[FEATURES].copy()
    y = df["addicted_label"].astype(int)

    numerical = [
        feature for feature in FEATURES
        if feature not in CATEGORICAL
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                StandardScaler(),
                numerical,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL,
            ),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "model",
                RandomForestClassifier(
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    parameter_grid = {
        "model__n_estimators": [200, 300],
        "model__max_depth": [None, 20],
        "model__min_samples_leaf": [1, 2, 4],
    }

    cv = StratifiedKFold(
        n_splits=3,
        shuffle=True,
        random_state=2026,
    )

    search = GridSearchCV(
        estimator=pipeline,
        param_grid=parameter_grid,
        scoring="roc_auc",
        cv=cv,
        n_jobs=-1,
        refit=True,
    )

    search.fit(X, y)

    output = {
        "method": "GridSearchCV",
        "purpose": "Classifier hyperparameter verification.",
        "dataset_rows": int(len(df)),
        "cv": "3-fold StratifiedKFold, shuffle=True, random_state=2026",
        "scoring": "roc_auc",
        "best_params": {
            key.replace("model__", ""): value
            for key, value in search.best_params_.items()
        },
        "best_mean_cv_roc_auc": float(search.best_score_),
        "important_note": (
            "This tuning score is not the final deployed evaluation. "
            "Use metrics.json for the fixed 5-fold out-of-fold classifier metrics."
        ),
    }

    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
