from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "usage_data(2).csv"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_RANDOM_STATE = 42
EVALUATION_RANDOM_STATE = 2026
DECISION_THRESHOLD = 0.78


def _classification_pipeline(
    feature_columns: list[str],
    categorical_columns: list[str],
) -> Pipeline:
    """Create the leakage-safe Random Forest classification pipeline."""

    numerical_columns = [
        column
        for column in feature_columns
        if column not in categorical_columns
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                StandardScaler(),
                numerical_columns,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_columns,
            ),
        ]
    )

    classifier = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=2,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=MODEL_RANDOM_STATE,
        n_jobs=-1,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", classifier),
        ]
    )


def _evaluate_classifier(
    y_true: pd.Series,
    probabilities: np.ndarray,
    threshold: float = DECISION_THRESHOLD,
) -> dict:
    """Evaluate out-of-fold probabilities at a locked decision threshold."""

    prediction = (probabilities >= threshold).astype(int)

    return {
        "decision_threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, prediction)),
        "balanced_accuracy": float(
            balanced_accuracy_score(y_true, prediction)
        ),
        "precision_class_1": float(
            precision_score(y_true, prediction, zero_division=0)
        ),
        "recall_class_1": float(
            recall_score(y_true, prediction, zero_division=0)
        ),
        "macro_f1": float(
            f1_score(y_true, prediction, average="macro")
        ),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision": float(
            average_precision_score(y_true, probabilities)
        ),
        "brier_score": float(
            brier_score_loss(y_true, probabilities)
        ),
        "evaluation": (
            "Fixed 5-fold stratified out-of-fold probabilities; "
            "decision threshold locked at 0.78 from prior development "
            "rather than re-optimized on the final OOF predictions."
        ),
    }


def main() -> None:
    """Train, evaluate, and save all local deployment artifacts."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}\n"
            "Place usage_data(2).csv inside the data folder."
        )

    df = pd.read_csv(DATA_PATH)

    required_columns = [
        "transaction_id",
        "user_id",
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
        "addiction_level",
        "addicted_label",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Dataset is missing required columns: {missing_columns}"
        )

    # ------------------------------------------------------------------
    # Leakage-safe classification feature set
    # ------------------------------------------------------------------
    # transaction_id and user_id are identifiers.
    # addiction_level is intentionally excluded because it almost directly
    # encodes addicted_label in this dataset and would create target leakage.
    feature_columns = [
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

    categorical_columns = [
        "gender",
        "stress_level",
        "academic_work_impact",
    ]

    X = df[feature_columns].copy()
    y = df["addicted_label"].astype(int).copy()

    classifier_pipeline = _classification_pipeline(
        feature_columns,
        categorical_columns,
    )

    evaluation_cv = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=EVALUATION_RANDOM_STATE,
    )

    # Every out-of-fold prediction is generated by a model that did not train
    # on that sample. This avoids evaluating the model on its own training rows.
    oof_probability = cross_val_predict(
        classifier_pipeline,
        X,
        y,
        cv=evaluation_cv,
        method="predict_proba",
        n_jobs=1,
    )[:, 1]

    decision_threshold = DECISION_THRESHOLD
    classifier_metrics = _evaluate_classifier(
        y,
        oof_probability,
        threshold=decision_threshold,
    )

    print("\n=== RANDOM FOREST: 5-FOLD OUT-OF-FOLD ===")
    for metric, value in classifier_metrics.items():
        if isinstance(value, float):
            print(f"{metric}: {value:.4f}")
        else:
            print(f"{metric}: {value}")

    # ------------------------------------------------------------------
    # Calibrated model for the displayed score
    # ------------------------------------------------------------------
    # The calibrated score improves score interpretability in the UI.
    # The locked Random Forest threshold remains the classification policy.
    calibrated_classifier = CalibratedClassifierCV(
        estimator=clone(
            classifier_pipeline
        ),
        method="isotonic",
        cv=5,
        n_jobs=-1,
    )

    # ------------------------------------------------------------------
    # Regression: estimate weekend screen time
    # ------------------------------------------------------------------
    # The provided dataset is cross-sectional rather than a true sequence of
    # repeated measurements per user. A supervised regressor is therefore more
    # defensible here than claiming an LSTM time-series model without sequences.
    regression_target = "weekend_screen_time"

    regression_features = [
        "age",
        "gender",
        "daily_screen_time_hours",
        "social_media_hours",
        "gaming_hours",
        "work_study_hours",
        "sleep_hours",
        "notifications_per_day",
        "app_opens_per_day",
        "stress_level",
        "academic_work_impact",
    ]

    regression_categorical = [
        "gender",
        "stress_level",
        "academic_work_impact",
    ]

    regression_numerical = [
        column
        for column in regression_features
        if column not in regression_categorical
    ]

    regression_preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                StandardScaler(),
                regression_numerical,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                regression_categorical,
            ),
        ]
    )

    regressor_pipeline = Pipeline(
        steps=[
            (
                "preprocessor",
                regression_preprocessor,
            ),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=120,
                    random_state=EVALUATION_RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    X_regression = df[regression_features].copy()
    y_regression = df[regression_target].astype(float).copy()

    (
        X_regression_train,
        X_regression_test,
        y_regression_train,
        y_regression_test,
    ) = train_test_split(
        X_regression,
        y_regression,
        test_size=0.20,
        random_state=EVALUATION_RANDOM_STATE,
    )

    regressor_pipeline.fit(
        X_regression_train,
        y_regression_train,
    )

    regression_prediction = regressor_pipeline.predict(
        X_regression_test
    )

    regression_metrics = {
        "mae": float(
            mean_absolute_error(
                y_regression_test,
                regression_prediction,
            )
        ),
        "rmse": float(
            np.sqrt(
                mean_squared_error(
                    y_regression_test,
                    regression_prediction,
                )
            )
        ),
        "r2": float(
            r2_score(
                y_regression_test,
                regression_prediction,
            )
        ),
    }

    print("\n=== REGRESSION: WEEKEND SCREEN-TIME ESTIMATE ===")
    for metric, value in regression_metrics.items():
        print(f"{metric}: {value:.4f}")

    # ------------------------------------------------------------------
    # K-Means user behavior segmentation
    # ------------------------------------------------------------------
    cluster_features = [
        "daily_screen_time_hours",
        "social_media_hours",
        "gaming_hours",
        "work_study_hours",
        "sleep_hours",
        "notifications_per_day",
        "app_opens_per_day",
        "weekend_screen_time",
    ]

    cluster_scaler = StandardScaler()
    cluster_matrix = cluster_scaler.fit_transform(
        df[cluster_features]
    )

    kmeans = KMeans(
        n_clusters=4,
        random_state=EVALUATION_RANDOM_STATE,
        n_init=20,
    )

    cluster_labels = kmeans.fit_predict(
        cluster_matrix
    )

    cluster_silhouette = float(
        silhouette_score(
            cluster_matrix,
            cluster_labels,
            sample_size=min(
                3000,
                len(df),
            ),
            random_state=EVALUATION_RANDOM_STATE,
        )
    )

    cluster_frame = df[cluster_features].copy()
    cluster_frame["cluster"] = cluster_labels

    cluster_profiles = (
        cluster_frame
        .groupby("cluster")[cluster_features]
        .mean()
        .round(2)
    )

    clustering_metrics = {
        "n_clusters": 4,
        "silhouette_score": cluster_silhouette,
    }

    # ------------------------------------------------------------------
    # Fit final deployment models on all competition rows
    # ------------------------------------------------------------------
    final_classifier = clone(
        classifier_pipeline
    )
    final_classifier.fit(X, y)

    train_probability = final_classifier.predict_proba(X)[:, 1]
    train_prediction = (train_probability >= decision_threshold).astype(int)
    train_roc_auc = float(roc_auc_score(y, train_probability))
    train_balanced_accuracy = float(
        balanced_accuracy_score(y, train_prediction)
    )
    classifier_metrics.update(
        {
            "train_roc_auc": train_roc_auc,
            "train_balanced_accuracy_at_threshold": train_balanced_accuracy,
            "roc_auc_generalization_gap": float(
                train_roc_auc - classifier_metrics["roc_auc"]
            ),
            "balanced_accuracy_generalization_gap": float(
                train_balanced_accuracy
                - classifier_metrics["balanced_accuracy"]
            ),
            "regularization": {
                "max_depth": 20,
                "min_samples_leaf": 2,
                "n_estimators": 300,
            },
        }
    )

    final_calibrated_classifier = calibrated_classifier
    final_calibrated_classifier.fit(X, y)

    final_regressor = clone(
        regressor_pipeline
    )
    final_regressor.fit(
        X_regression,
        y_regression,
    )

    reference_features = [
        "daily_screen_time_hours",
        "social_media_hours",
        "weekend_screen_time",
        "notifications_per_day",
        "gaming_hours",
        "sleep_hours",
        "work_study_hours",
        "app_opens_per_day",
    ]

    reference_data = {
        "feature_columns": feature_columns,
        "regression_features": regression_features,
        "cluster_features": cluster_features,
        "reference_distributions": {
            feature: sorted(
                df[feature].astype(float).tolist()
            )
            for feature in reference_features
        },
        "categorical_options": {
            "gender": sorted(
                df["gender"].dropna().unique().tolist()
            ),
            "stress_level": sorted(
                df["stress_level"].dropna().unique().tolist()
            ),
            "academic_work_impact": sorted(
                df["academic_work_impact"]
                .dropna()
                .unique()
                .tolist()
            ),
        },
        "dataset_size": int(len(df)),
        "note": (
            "Percentiles are relative to the competition dataset "
            "and are not medical thresholds."
        ),
    }

    metrics = {
        "classifier": classifier_metrics,
        "calibrated_classifier": {
            "purpose": (
                "Used only for the displayed Model Risk Score; the Random Forest "
                "probability and locked threshold determine the risk class."
            ),
            "method": "isotonic",
            "cv": 5,
        },
        "regressor": regression_metrics,
        "clustering": clustering_metrics,
    }

    training_metadata = {
        "trained_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_random_state": MODEL_RANDOM_STATE,
        "evaluation_random_state": EVALUATION_RANDOM_STATE,
        "dataset_rows": int(len(df)),
        "classification_features": feature_columns,
        "decision_threshold": decision_threshold,
        "leakage_columns_excluded": [
            "transaction_id",
            "user_id",
            "addiction_level",
        ],
        "notes": [
            "Random Forest is the primary classifier.",
            "Classifier regularization uses max_depth=20 and min_samples_leaf=2 to reduce train-vs-OOF overfitting while preserving validation performance.",
            "The classification decision threshold is locked at 0.78 and is not re-optimized on the final OOF predictions.",
            "Isotonic calibration is used for the displayed Model Risk Score.",
            "The score is not a medical probability or diagnosis.",
            "LSTM is not used because the provided dataset does not contain true per-user longitudinal sequences.",
        ],
    }

    joblib.dump(
        final_classifier,
        MODELS_DIR / "digital_wellness_rf.joblib",
        compress=3,
    )
    joblib.dump(
        final_calibrated_classifier,
        MODELS_DIR / "digital_wellness_isotonic.joblib",
        compress=3,
    )
    joblib.dump(
        final_regressor,
        MODELS_DIR / "weekend_screen_regressor.joblib",
        compress=3,
    )
    joblib.dump(
        cluster_scaler,
        MODELS_DIR / "cluster_scaler.joblib",
        compress=3,
    )
    joblib.dump(
        kmeans,
        MODELS_DIR / "behavior_kmeans.joblib",
        compress=3,
    )
    joblib.dump(
        cluster_profiles,
        MODELS_DIR / "cluster_profiles.joblib",
        compress=3,
    )
    joblib.dump(
        reference_data,
        MODELS_DIR / "wellness_reference_data.joblib",
        compress=3,
    )

    with open(
        MODELS_DIR / "decision_policy.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "decision_threshold": decision_threshold,
                "selection_metric": "locked_development_threshold",
                "source": "prior_development_policy",
            },
            file,
            indent=2,
        )

    with open(
        MODELS_DIR / "metrics.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metrics,
            file,
            indent=2,
        )

    with open(
        MODELS_DIR / "training_metadata.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            training_metadata,
            file,
            indent=2,
        )

    print("\nAll local deployment artifacts were saved to:")
    print(MODELS_DIR)


if __name__ == "__main__":
    main()
