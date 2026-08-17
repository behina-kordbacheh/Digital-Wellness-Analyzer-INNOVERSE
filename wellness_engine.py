from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import shap


BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"


# ----------------------------------------------------------------------
# Model loading
# ----------------------------------------------------------------------

def _load_artifacts() -> dict:
    """Load all local model artifacts and fail with a clear message."""

    required_files = [
        "digital_wellness_rf.joblib",
        "digital_wellness_isotonic.joblib",
        "weekend_screen_regressor.joblib",
        "cluster_scaler.joblib",
        "behavior_kmeans.joblib",
        "cluster_profiles.joblib",
        "wellness_reference_data.joblib",
        "decision_policy.json",
    ]

    missing_files = [
        filename
        for filename in required_files
        if not (MODELS_DIR / filename).exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Model files are missing. Run python train_models.py first. "
            f"Missing: {missing_files}"
        )

    return {
        "rf_model": joblib.load(
            MODELS_DIR / "digital_wellness_rf.joblib"
        ),
        "risk_model": joblib.load(
            MODELS_DIR / "digital_wellness_isotonic.joblib"
        ),
        "regressor": joblib.load(
            MODELS_DIR / "weekend_screen_regressor.joblib"
        ),
        "cluster_scaler": joblib.load(
            MODELS_DIR / "cluster_scaler.joblib"
        ),
        "kmeans": joblib.load(
            MODELS_DIR / "behavior_kmeans.joblib"
        ),
        "cluster_profiles": joblib.load(
            MODELS_DIR / "cluster_profiles.joblib"
        ),
        "reference_data": joblib.load(
            MODELS_DIR / "wellness_reference_data.joblib"
        ),
        "decision_policy": json.loads(
            (MODELS_DIR / "decision_policy.json").read_text(encoding="utf-8")
        ),
    }


_ARTIFACTS = _load_artifacts()

rf_model = _ARTIFACTS["rf_model"]
risk_model = _ARTIFACTS["risk_model"]
regressor = _ARTIFACTS["regressor"]
cluster_scaler = _ARTIFACTS["cluster_scaler"]
kmeans = _ARTIFACTS["kmeans"]
cluster_profiles = _ARTIFACTS["cluster_profiles"]
reference_data = _ARTIFACTS["reference_data"]
decision_policy = _ARTIFACTS["decision_policy"]

# The decision threshold is stored with the model artifacts so the web app
# uses the same policy that was selected during out-of-fold evaluation.
DECISION_THRESHOLD = float(
    decision_policy.get("decision_threshold", 0.78)
)


# ----------------------------------------------------------------------
# Core model helpers
# ----------------------------------------------------------------------

def _as_model_frame(user_data: dict) -> pd.DataFrame:
    """Create one inference row in the exact training feature order."""

    frame = pd.DataFrame([user_data])
    return frame[reference_data["feature_columns"]]


def predict_user(user_data: dict) -> dict:
    """Return classification plus raw and calibrated model scores."""

    user_frame = _as_model_frame(user_data)

    raw_risk_score = float(
        rf_model.predict_proba(user_frame)[0, 1]
    )

    risk_class = int(
        raw_risk_score >= DECISION_THRESHOLD
    )

    calibrated_risk_score = float(
        risk_model.predict_proba(user_frame)[0, 1]
    )

    if risk_class == 1:
        wellness_status = "Needs attention"
        label = "Higher-risk digital usage pattern"
    else:
        wellness_status = "More balanced"
        label = "Lower-risk digital usage pattern"

    return {
        "risk_class": risk_class,
        "wellness_status": wellness_status,
        "label": label,
        "raw_risk_score": raw_risk_score,
        "calibrated_risk_score": calibrated_risk_score,
        "lower_risk_share": max(
            0.0,
            1.0 - calibrated_risk_score,
        ),
    }


def percentile(feature_name: str, value: float) -> float:
    """Calculate a dataset-relative percentile for one numeric feature."""

    values = reference_data[
        "reference_distributions"
    ][feature_name]

    return (
        bisect_right(values, float(value))
        / len(values)
        * 100.0
    )


def predict_weekend_screen_time(user_data: dict) -> float:
    """Estimate weekend screen time from the current behavior profile."""

    frame = pd.DataFrame([user_data])
    frame = frame[
        reference_data["regression_features"]
    ]

    return float(
        regressor.predict(frame)[0]
    )


def get_behavior_cluster(user_data: dict) -> dict:
    """Assign the user to one K-Means behavior segment."""

    cluster_features = reference_data[
        "cluster_features"
    ]

    row = pd.DataFrame(
        [[user_data[feature] for feature in cluster_features]],
        columns=cluster_features,
    )

    scaled_row = cluster_scaler.transform(row)
    cluster_id = int(
        kmeans.predict(scaled_row)[0]
    )

    profile = (
        cluster_profiles
        .loc[cluster_id]
        .to_dict()
    )

    return {
        "cluster_id": cluster_id,
        "profile": profile,
    }


# ----------------------------------------------------------------------
# Explainable AI
# ----------------------------------------------------------------------

def explain_user_prediction(
    user_data: dict,
    top_n: int = 5,
) -> list[dict]:
    """Explain the Random Forest class-1 decision with SHAP values."""

    user_frame = _as_model_frame(user_data)

    preprocessor = rf_model.named_steps[
        "preprocessor"
    ]
    forest = rf_model.named_steps[
        "model"
    ]

    processed_user = preprocessor.transform(
        user_frame
    )

    transformed_names = (
        preprocessor.get_feature_names_out()
    )

    explainer = shap.TreeExplainer(forest)
    shap_values = explainer.shap_values(
        processed_user
    )

    if isinstance(shap_values, np.ndarray):
        if shap_values.ndim == 3:
            class_1_values = shap_values[0, :, 1]
        elif shap_values.ndim == 2:
            class_1_values = shap_values[0]
        else:
            raise ValueError(
                "Unexpected SHAP output shape."
            )
    elif isinstance(shap_values, list):
        class_1_values = shap_values[1][0]
    else:
        raise ValueError(
            "Unsupported SHAP output format."
        )

    categorical_features = [
        "gender",
        "stress_level",
        "academic_work_impact",
    ]

    aggregated_shap: dict[str, float] = {}

    for transformed_name, shap_value in zip(
        transformed_names,
        class_1_values,
    ):
        if transformed_name.startswith(
            "numeric__"
        ):
            original_feature = (
                transformed_name.replace(
                    "numeric__",
                    "",
                    1,
                )
            )

        elif transformed_name.startswith(
            "categorical__"
        ):
            cleaned_name = transformed_name.replace(
                "categorical__",
                "",
                1,
            )

            original_feature = cleaned_name

            for categorical_feature in categorical_features:
                if cleaned_name.startswith(
                    categorical_feature + "_"
                ):
                    original_feature = (
                        categorical_feature
                    )
                    break
        else:
            original_feature = transformed_name

        aggregated_shap[original_feature] = (
            aggregated_shap.get(
                original_feature,
                0.0,
            )
            + float(shap_value)
        )

    explanation = [
        {
            "feature": feature,
            "shap_value": value,
            "direction": (
                "increases model risk"
                if value > 0
                else "decreases model risk"
            ),
        }
        for feature, value in aggregated_shap.items()
    ]

    explanation.sort(
        key=lambda item: abs(
            item["shap_value"]
        ),
        reverse=True,
    )

    return explanation[:top_n]


# ----------------------------------------------------------------------
# Activity replacement library
# ----------------------------------------------------------------------

ACTIVITY_LIBRARY = {
    "Student": {
        "Learning": [
            "Review flashcards away from social media.",
            "Plan the next study block on paper.",
            "Read 5-10 pages of a course book.",
            "Practice one small problem from your current subject.",
        ],
        "Physical": [
            "Take a brisk walk without holding your phone.",
            "Do a short mobility or stretching session.",
            "Walk around campus or your neighborhood.",
        ],
        "Relaxation": [
            "Make tea and sit away from screens for a few minutes.",
            "Try a short breathing or mindfulness break.",
            "Listen to calm audio with the screen locked.",
        ],
        "Social": [
            "Call a friend instead of scrolling.",
            "Have a short face-to-face conversation.",
            "Study with a friend offline.",
        ],
        "Creative": [
            "Sketch or journal for a few minutes.",
            "Write ideas for a personal project.",
            "Practice a musical instrument.",
        ],
    },
    "Software / IT": {
        "Learning": [
            "Write your next coding task on paper before opening another tab.",
            "Review one technical concept away from social feeds.",
            "Sketch an algorithm or system flow before coding.",
        ],
        "Physical": [
            "Stand up and stretch your neck, shoulders, wrists, and back.",
            "Take a short walk away from your workstation.",
            "Do a quick mobility routine.",
        ],
        "Relaxation": [
            "Look away from screens and rest your eyes.",
            "Sit quietly for a few minutes without notifications.",
            "Use a short breathing break between work blocks.",
        ],
        "Social": [
            "Talk to a coworker or friend offline.",
            "Take a coffee break without opening social apps.",
        ],
        "Creative": [
            "Sketch a UI or system idea on paper.",
            "Brainstorm a side-project feature offline.",
        ],
    },
    "Office Work": {
        "Learning": [
            "Read a few pages of a book or professional note.",
            "Write tomorrow's top three priorities.",
            "Review one useful work skill for a few minutes.",
        ],
        "Physical": [
            "Walk around the office or outside.",
            "Stretch your shoulders, hips, and back.",
            "Take the stairs for a short movement break.",
        ],
        "Relaxation": [
            "Make a drink and take a screen-free break.",
            "Practice a short breathing exercise.",
        ],
        "Social": [
            "Have a short conversation with a colleague.",
            "Call someone instead of checking social media.",
        ],
        "Creative": [
            "Journal or write a few ideas by hand.",
            "Sketch a process improvement idea.",
        ],
    },
    "Teacher": {
        "Learning": [
            "Read a few pages related to your subject.",
            "Plan one classroom activity on paper.",
            "Reflect on one thing that worked well today.",
        ],
        "Physical": [
            "Take a short walk.",
            "Do a gentle stretching routine.",
        ],
        "Relaxation": [
            "Sit somewhere quiet without a screen.",
            "Try a brief breathing exercise.",
        ],
        "Social": [
            "Call a friend or family member.",
            "Have a short face-to-face conversation.",
        ],
        "Creative": [
            "Design a classroom idea on paper.",
            "Journal about a teaching idea.",
        ],
    },
    "Healthcare": {
        "Learning": [
            "Read a short professional note away from social media.",
            "Reflect on one learning point from your day.",
        ],
        "Physical": [
            "Take a short walk if your schedule allows.",
            "Do gentle stretching after a long shift.",
        ],
        "Relaxation": [
            "Sit quietly for a few minutes without notifications.",
            "Use a short breathing exercise.",
        ],
        "Social": [
            "Have a brief conversation with someone you trust.",
            "Call a friend instead of scrolling.",
        ],
        "Creative": [
            "Journal briefly about your day.",
            "Do a simple creative activity away from a screen.",
        ],
    },
    "Creative Work": {
        "Learning": [
            "Study one reference image, page, or concept intentionally.",
            "Write down three new ideas away from social feeds.",
        ],
        "Physical": [
            "Take a walk and observe your surroundings.",
            "Stretch and reset your posture.",
        ],
        "Relaxation": [
            "Listen to music with your screen locked.",
            "Take a quiet screen-free break.",
        ],
        "Social": [
            "Talk to another creative person offline.",
            "Call a friend instead of scrolling.",
        ],
        "Creative": [
            "Sketch, write, photograph, or create something offline.",
            "Make a small low-pressure creative experiment.",
        ],
    },
    "Freelancer": {
        "Learning": [
            "Review one professional skill or client note.",
            "Plan your next work block on paper.",
        ],
        "Physical": [
            "Take a short walk away from your desk.",
            "Do a mobility or stretching session.",
        ],
        "Relaxation": [
            "Take a real break without switching to social media.",
            "Sit somewhere different from your work area.",
        ],
        "Social": [
            "Call someone intentionally instead of browsing feeds.",
            "Have a short offline conversation.",
        ],
        "Creative": [
            "Brainstorm a new project idea on paper.",
            "Work on a small personal project for a few minutes.",
        ],
    },
    "Homemaker": {
        "Learning": [
            "Read a few pages of something you enjoy.",
            "Learn one small practical skill offline.",
        ],
        "Physical": [
            "Take a short walk.",
            "Do a light stretching or movement session.",
        ],
        "Relaxation": [
            "Make a drink and sit without your phone.",
            "Try a short mindfulness break.",
        ],
        "Social": [
            "Call or visit someone you care about.",
            "Have a screen-free conversation.",
        ],
        "Creative": [
            "Cook, draw, journal, garden, or make something by hand.",
            "Spend a few minutes on a personal hobby.",
        ],
    },
    "Other": {
        "Learning": [
            "Read a few pages of a book.",
            "Learn or practice one small useful skill.",
        ],
        "Physical": [
            "Take a short walk.",
            "Stretch or move for a few minutes.",
        ],
        "Relaxation": [
            "Sit quietly away from screens.",
            "Try a short breathing exercise.",
        ],
        "Social": [
            "Call or talk with someone offline.",
            "Spend a few minutes with family or friends.",
        ],
        "Creative": [
            "Journal, sketch, cook, or work on a hobby.",
            "Create something small away from a screen.",
        ],
    },
}


TIME_GUIDANCE = {
    "5 minutes": 1,
    "15 minutes": 2,
    "30 minutes": 3,
    "60+ minutes": 4,
}


FOCUS_TOOL_LIBRARY = [
    {
        "name": "Forest",
        "best_for": "Focus sessions and intentional phone-free time",
        "why": (
            "Uses a visual focus timer to encourage staying with one task "
            "instead of repeatedly checking distracting apps."
        ),
        "platforms": [
            "Any",
            "Android",
            "iPhone / iPad",
        ],
        "website": "https://www.forestapp.cc/",
    },
    {
        "name": "Freedom",
        "best_for": "Blocking distracting apps and websites across devices",
        "why": (
            "Useful when the main problem is access to distracting websites "
            "or apps during study and work sessions."
        ),
        "platforms": [
            "Any",
            "Windows",
            "Mac",
            "Android",
            "iPhone / iPad",
        ],
        "website": "https://freedom.to/",
    },
    {
        "name": "Cold Turkey",
        "best_for": "Strong desktop distraction blocking",
        "why": (
            "Useful for users who need a stricter website or application "
            "blocking environment while studying or working."
        ),
        "platforms": [
            "Any",
            "Windows",
            "Mac",
        ],
        "website": "https://getcoldturkey.com/",
    },
    {
        "name": "one sec",
        "best_for": "Interrupting automatic social-media opening",
        "why": (
            "Adds a deliberate pause before distracting app use, which can "
            "help users notice automatic scrolling habits."
        ),
        "platforms": [
            "Any",
            "Android",
            "iPhone / iPad",
        ],
        "website": "https://one-sec.app/",
    },
]


def _choose_activity_categories(
    goal: str,
    activity_preference: str,
) -> list[str]:
    """Prioritize activity categories from goal and preference."""

    preference_map = {
        "Physical": ["Physical"],
        "Social": ["Social"],
        "Creative": ["Creative"],
        "Learning": ["Learning"],
        "Relaxation": ["Relaxation"],
        "Mixed": [
            "Physical",
            "Learning",
            "Relaxation",
            "Social",
            "Creative",
        ],
    }

    goal_map = {
        "Focus": ["Learning", "Relaxation"],
        "Relax": ["Relaxation", "Physical"],
        "Be more active": ["Physical"],
        "Learn something": [
            "Learning",
            "Creative",
        ],
        "Sleep better": [
            "Relaxation",
            "Physical",
        ],
        "Reduce social media": [
            "Physical",
            "Social",
            "Creative",
            "Learning",
            "Relaxation",
        ],
    }

    categories: list[str] = []

    for category in preference_map.get(
        activity_preference,
        ["Physical", "Learning", "Relaxation"],
    ):
        if category not in categories:
            categories.append(category)

    for category in goal_map.get(goal, []):
        if category not in categories:
            categories.append(category)

    return categories


def recommend_focus_tools(
    device_platform: str,
    goal: str,
    social_media_reason: str,
) -> list[dict]:
    """Recommend focus software without making it part of the ML model."""

    matching_tools = [
        tool
        for tool in FOCUS_TOOL_LIBRARY
        if (
            device_platform in tool["platforms"]
            or "Any" in tool["platforms"]
        )
    ]

    # Prioritize intervention style according to the user's main trigger.
    priority_names: list[str]

    if social_media_reason == "Habit":
        priority_names = [
            "one sec",
            "Forest",
            "Freedom",
            "Cold Turkey",
        ]
    elif goal == "Focus":
        priority_names = [
            "Forest",
            "Freedom",
            "Cold Turkey",
            "one sec",
        ]
    else:
        priority_names = [
            "Freedom",
            "Forest",
            "one sec",
            "Cold Turkey",
        ]

    rank = {
        name: index
        for index, name in enumerate(priority_names)
    }

    matching_tools.sort(
        key=lambda tool: rank.get(
            tool["name"],
            999,
        )
    )

    return matching_tools[:3]


def smart_activity_replacements(
    user_data: dict,
    personalization: dict,
) -> dict:
    """Create realistic alternatives to passive social-media use."""

    occupation = personalization.get(
        "occupation",
        "Other",
    )
    available_time = personalization.get(
        "available_time",
        "15 minutes",
    )
    goal = personalization.get(
        "goal",
        "Reduce social media",
    )
    activity_preference = personalization.get(
        "activity_preference",
        "Mixed",
    )
    peak_usage_time = personalization.get(
        "peak_usage_time",
        "Evening",
    )
    social_media_reason = personalization.get(
        "social_media_reason",
        "Habit",
    )
    device_platform = personalization.get(
        "device_platform",
        "Any",
    )

    activity_profile = ACTIVITY_LIBRARY.get(
        occupation,
        ACTIVITY_LIBRARY["Other"],
    )

    categories = _choose_activity_categories(
        goal,
        activity_preference,
    )

    max_suggestions = TIME_GUIDANCE.get(
        available_time,
        2,
    )

    suggestions: list[dict] = []

    for category in categories:
        for activity in activity_profile.get(
            category,
            [],
        ):
            suggestions.append(
                {
                    "category": category,
                    "activity": activity,
                }
            )

            if len(suggestions) >= max_suggestions:
                break

        if len(suggestions) >= max_suggestions:
            break

    social_media_percentile = percentile(
        "social_media_hours",
        user_data["social_media_hours"],
    )

    challenge_minutes = {
        "5 minutes": 5,
        "15 minutes": 15,
        "30 minutes": 30,
        "60+ minutes": 45,
    }.get(
        available_time,
        15,
    )

    first_activity = (
        suggestions[0]["activity"]
        if suggestions
        else "Take a short screen-free break."
    )

    daily_challenge = (
        f"Replace {challenge_minutes} minutes of passive "
        f"social-media use with this activity: {first_activity}"
    )

    timing_tips = {
        "Morning": (
            "Protect the first part of your morning from automatic scrolling. "
            "Start with water, movement, breakfast, or a short plan for the day."
        ),
        "Afternoon": (
            "Use a planned afternoon reset instead of opening social media automatically. "
            "A short walk, stretch, or focused break can interrupt the habit loop."
        ),
        "Evening": (
            "Create a clear evening screen boundary. Choose one intentional offline activity "
            "before returning to entertainment."
        ),
        "Late night": (
            "Late-night scrolling can compete with your sleep routine. Try a phone-free "
            "wind-down period and keep the device away from the bed when practical."
        ),
    }

    reason_tips = {
        "Boredom": (
            "Because boredom is the trigger, choose something easy to start: movement, "
            "a tiny creative task, a short walk, or a quick learning challenge."
        ),
        "Habit": (
            "Because the behavior feels automatic, add friction: move social apps off the "
            "home screen, turn off non-essential notifications, and choose a specific check-in time."
        ),
        "Relaxation": (
            "If social media is used to relax, replace some sessions with genuinely restorative "
            "activities such as music with the screen locked, breathing, stretching, or tea."
        ),
        "Communication": (
            "If connection is the goal, shift from passive feed consumption to intentional contact: "
            "message one person, make a short call, or meet someone offline."
        ),
        "Work / Study": (
            "If social platforms are necessary for work or study, separate intentional task use "
            "from feed browsing with scheduled communication windows."
        ),
    }

    contextual_tip = (
        f"{timing_tips.get(peak_usage_time, '')} "
        f"{reason_tips.get(social_media_reason, '')}"
    ).strip()

    return {
        "occupation": occupation,
        "available_time": available_time,
        "goal": goal,
        "activity_preference": activity_preference,
        "peak_usage_time": peak_usage_time,
        "social_media_reason": social_media_reason,
        "device_platform": device_platform,
        "social_media_context": {
            "hours": float(
                user_data["social_media_hours"]
            ),
            "percentile": social_media_percentile,
        },
        "suggestions": suggestions,
        "contextual_tip": contextual_tip,
        "focus_tools": recommend_focus_tools(
            device_platform=device_platform,
            goal=goal,
            social_media_reason=social_media_reason,
        ),
        "daily_challenge": daily_challenge,
    }


# ----------------------------------------------------------------------
# Recommendation logic
# ----------------------------------------------------------------------

def generate_recommendations(
    user_data: dict,
    personalization: dict,
) -> list[str]:
    """Combine SHAP, percentiles, and user context into suggestions."""

    explanations = explain_user_prediction(
        user_data,
        top_n=12,
    )

    shap_map = {
        item["feature"]: item["shap_value"]
        for item in explanations
    }

    recommendations: list[str] = []

    daily_percentile = percentile(
        "daily_screen_time_hours",
        user_data["daily_screen_time_hours"],
    )
    weekend_percentile = percentile(
        "weekend_screen_time",
        user_data["weekend_screen_time"],
    )
    social_percentile = percentile(
        "social_media_hours",
        user_data["social_media_hours"],
    )
    notification_percentile = percentile(
        "notifications_per_day",
        user_data["notifications_per_day"],
    )

    daily_shap = shap_map.get(
        "daily_screen_time_hours",
        0.0,
    )
    weekend_shap = shap_map.get(
        "weekend_screen_time",
        0.0,
    )
    social_shap = shap_map.get(
        "social_media_hours",
        0.0,
    )

    if (
        daily_shap > 0.01
        and daily_percentile >= 50
    ):
        if daily_percentile >= 75:
            recommendations.append(
                "Daily screen time is relatively high in the reference dataset and strongly contributes "
                "to the model score. Introduce one or two scheduled screen-free blocks and reduce "
                "non-essential use gradually rather than attempting an extreme digital detox."
            )
        else:
            recommendations.append(
                "Daily screen time is not among the highest values in the reference dataset, but it is a "
                "strong driver of this model result. Review which screen activities are essential and "
                "replace one low-value session with an offline activity."
            )

    if (
        weekend_shap > 0.01
        and weekend_percentile >= 75
    ):
        recommendations.append(
            "Weekend screen time is relatively high and contributes to the model result. Schedule a "
            "specific offline block for movement, social contact, learning, or a hobby."
        )

    if (
        social_shap > 0.01
        and social_percentile >= 75
    ):
        recommendations.append(
            "Social-media use is relatively high and contributes to the model result. Replace one passive "
            "scrolling session with an intentional activity and consider a focus/blocking tool during that time."
        )

    if notification_percentile >= 80:
        recommendations.append(
            "Notification volume is high relative to the reference dataset. Turn off non-essential alerts "
            "and batch communication into planned check-in windows when possible."
        )

    if personalization.get(
        "peak_usage_time"
    ) == "Late night":
        recommendations.append(
            "You reported that your heaviest scrolling happens late at night. Create a predictable wind-down "
            "period and move entertainment use earlier when practical."
        )

    if not recommendations:
        recommendations.append(
            "No major actionable screen-use pattern was identified by the current model. Continue monitoring "
            "your habits, keep intentional boundaries, and review the trend again at your next check-in."
        )

    return recommendations


# ----------------------------------------------------------------------
# Descriptive balance breakdown for visualization
# ----------------------------------------------------------------------

def build_balance_breakdown(user_data: dict) -> dict:
    """Create descriptive chart values; these are not additional ML targets."""

    daily_screen = max(
        float(user_data["daily_screen_time_hours"]),
        0.01,
    )

    productive_share = min(
        float(user_data["work_study_hours"])
        / daily_screen
        * 100.0,
        100.0,
    )

    recreation_hours = (
        float(user_data["social_media_hours"])
        + float(user_data["gaming_hours"])
    )

    recreation_share = min(
        recreation_hours
        / daily_screen
        * 100.0,
        100.0,
    )

    sleep_percentile = percentile(
        "sleep_hours",
        user_data["sleep_hours"],
    )

    return {
        "productive_share": round(
            productive_share,
            1,
        ),
        "recreation_share": round(
            recreation_share,
            1,
        ),
        "sleep_percentile": round(
            sleep_percentile,
            1,
        ),
        "usage_hours": {
            "Daily screen": float(
                user_data["daily_screen_time_hours"]
            ),
            "Social media": float(
                user_data["social_media_hours"]
            ),
            "Gaming": float(
                user_data["gaming_hours"]
            ),
            "Work / study": float(
                user_data["work_study_hours"]
            ),
            "Sleep": float(
                user_data["sleep_hours"]
            ),
            "Weekend screen": float(
                user_data["weekend_screen_time"]
            ),
        },
        "note": (
            "This chart is descriptive. It visualizes the user's reported time allocation and dataset-relative sleep percentile; "
            "it is not a clinical health score."
        ),
    }



# ----------------------------------------------------------------------
# Lifestyle planning, productive digital use, and ergonomic guidance
# ----------------------------------------------------------------------

def build_productive_digital_context(
    user_data: dict,
    personalization: dict,
) -> dict:
    """Describe purposeful screen use separately from the validated ML risk model."""

    study_hours = max(
        0.0,
        float(personalization.get("digital_study_hours", 0.0) or 0.0),
    )
    work_hours = max(
        0.0,
        float(personalization.get("digital_work_hours", 0.0) or 0.0),
    )
    daily_screen = max(
        0.01,
        float(user_data["daily_screen_time_hours"]),
    )

    purposeful_hours = min(
        study_hours + work_hours,
        daily_screen,
    )
    purposeful_share = min(
        purposeful_hours / daily_screen * 100.0,
        100.0,
    )

    # This is intentionally a descriptive product metric, not a trained health score.
    intentional_use_score = round(purposeful_share, 1)

    return {
        "digital_study_hours": round(study_hours, 2),
        "digital_work_hours": round(work_hours, 2),
        "purposeful_hours": round(purposeful_hours, 2),
        "purposeful_share": round(purposeful_share, 1),
        "intentional_use_score": intentional_use_score,
        "message": (
            "Purposeful work/study screen time receives positive context in this "
            "descriptive score. It does not override or alter the validated ML classifier."
        ),
    }


def build_exercise_context(
    user_data: dict,
    personalization: dict,
) -> dict:
    """Create a conservative activity summary without inventing mood-effect percentages."""

    exercise_days = max(
        0,
        min(
            int(personalization.get("exercise_days_per_week", 0) or 0),
            7,
        ),
    )
    exercise_minutes = max(
        0,
        int(personalization.get("exercise_minutes_per_session", 0) or 0),
    )
    weekly_minutes = exercise_days * exercise_minutes

    if int(user_data.get("age", 18)) >= 18:
        if weekly_minutes >= 150:
            progress_label = "Meets the common adult 150-minute weekly activity benchmark."
        elif weekly_minutes > 0:
            progress_label = (
                f"Current plan: {weekly_minutes} minutes per week. "
                "For adults, a common public-health benchmark is at least 150 minutes "
                "of moderate activity per week, adjusted to ability and health status."
            )
        else:
            progress_label = (
                "No exercise time is currently planned. Start only with an amount "
                "that is realistic and appropriate for your ability."
            )
    else:
        progress_label = (
            "This prototype does not prescribe adult exercise targets for users under 18."
        )

    return {
        "days_per_week": exercise_days,
        "minutes_per_session": exercise_minutes,
        "weekly_minutes": weekly_minutes,
        "progress_label": progress_label,
        "impact_note": (
            "Physical activity can support mood, sleep, and thinking, but this app does "
            "not claim that a fixed number of exercise minutes causes a specific percentage "
            "change in mood. Your daily check-ins can show your own observed pattern."
        ),
    }


def build_weekly_plan(
    personalization: dict,
) -> list[dict]:
    """Create a practical seven-day schedule from the user's selected activities."""

    if personalization.get("wants_weekly_plan", "No") != "Yes":
        return []

    selected = personalization.get("selected_activities", [])
    if isinstance(selected, str):
        selected = [selected]

    selected = set(selected)
    exercise_days = max(
        0,
        min(
            int(personalization.get("exercise_days_per_week", 0) or 0),
            7,
        ),
    )
    exercise_minutes = max(
        10,
        int(personalization.get("exercise_minutes_per_session", 20) or 20),
    )
    study_hours = max(
        0.0,
        float(personalization.get("study_hours_per_day", 0.0) or 0.0),
    )
    work_hours = max(
        0.0,
        float(personalization.get("work_hours_per_day", 0.0) or 0.0),
    )
    entertainment_hours = max(
        0.0,
        float(personalization.get("entertainment_hours_per_day", 0.0) or 0.0),
    )
    offline_social_minutes = max(
        0,
        int(personalization.get("offline_social_minutes", 0) or 0),
    )

    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    exercise_indices = []
    if exercise_days:
        # Spread exercise sessions across the week rather than stacking them.
        exercise_indices = sorted(
            {
                min(6, round(index * 6 / max(exercise_days - 1, 1)))
                for index in range(exercise_days)
            }
        )
        while len(exercise_indices) < exercise_days:
            for candidate in range(7):
                if candidate not in exercise_indices:
                    exercise_indices.append(candidate)
                    if len(exercise_indices) == exercise_days:
                        break
        exercise_indices = sorted(exercise_indices)

    plan = []

    for index, day in enumerate(day_names):
        blocks = []

        if "Study" in selected and study_hours > 0:
            blocks.append(
                f"{study_hours:g} h focused study in 1-2 distraction-light blocks"
            )

        if "Work" in selected and work_hours > 0:
            blocks.append(
                f"{work_hours:g} h planned work with notification batching"
            )

        if "Exercise" in selected and index in exercise_indices:
            blocks.append(
                f"{exercise_minutes} min movement/exercise at a comfortable intensity"
            )

        if "Entertainment" in selected and entertainment_hours > 0:
            blocks.append(
                f"{entertainment_hours:g} h intentional entertainment after priority tasks"
            )

        if "Offline Social" in selected and offline_social_minutes > 0:
            blocks.append(
                f"{offline_social_minutes} min offline social connection"
            )

        if "Reading" in selected:
            blocks.append("15-20 min reading away from feeds")

        if "Creative" in selected:
            blocks.append("15-30 min creative or hobby time")

        if "Mindfulness" in selected:
            blocks.append("5-10 min quiet reflection or breathing")

        if not blocks:
            blocks.append("Keep one short screen-free recovery block.")

        plan.append(
            {
                "day": day,
                "blocks": blocks,
            }
        )

    return plan


def build_friendly_coach_message(
    user_data: dict,
    personalization: dict,
    activity_replacements: dict,
) -> str:
    """Write a supportive, non-clinical message that feels human rather than robotic."""

    goal = personalization.get("goal", "Reduce social media")
    available_time = personalization.get("available_time", "15 minutes")
    first_activity = (
        activity_replacements["suggestions"][0]["activity"]
        if activity_replacements.get("suggestions")
        else "take a short phone-free break"
    )

    return (
        f"You do not need a perfect digital detox to make progress. "
        f"Start with just {available_time}: {first_activity} "
        f"That small replacement directly supports your goal to {goal.lower()}. "
        "Keep checking your own focus and mood; the useful question is whether this "
        "change helps you feel more intentional and get more of your real priorities done."
    )


def build_ergonomic_guidance() -> list[dict]:
    """Return conservative workstation guidance based on standard ergonomics principles."""

    return [
        {
            "title": "Screen position",
            "text": (
                "Keep the top of the monitor at or slightly below eye level and position "
                "the screen so your head and neck can stay neutral."
            ),
        },
        {
            "title": "Chair and feet",
            "text": (
                "Support your lower back and keep your feet flat on the floor or on a footrest."
            ),
        },
        {
            "title": "Arms and wrists",
            "text": (
                "Keep shoulders relaxed, elbows near the body, and wrists roughly in line "
                "with the forearms while typing."
            ),
        },
        {
            "title": "Eye comfort",
            "text": (
                "Use regular visual breaks, blink often, reduce glare, and adjust text size "
                "or room lighting when needed."
            ),
        },
        {
            "title": "About blue-light glasses",
            "text": (
                "Do not present blue-light glasses as protection from harmful computer "
                "radiation. Current ophthalmology guidance does not require special blue-light "
                "glasses for computer use; prescription eyewear should be chosen with an eye-care professional."
            ),
        },
    ]

def full_analysis(
    user_data: dict,
    personalization: dict | None = None,
) -> dict:
    """Run the complete local Digital Wellness analysis pipeline."""

    personalization = personalization or {}

    classification = predict_user(user_data)
    weekend_prediction = predict_weekend_screen_time(
        user_data
    )
    cluster = get_behavior_cluster(user_data)
    explanation = explain_user_prediction(user_data)
    recommendations = generate_recommendations(
        user_data,
        personalization,
    )
    activity_replacements = (
        smart_activity_replacements(
            user_data,
            personalization,
        )
    )
    productive_digital = build_productive_digital_context(
        user_data,
        personalization,
    )
    exercise_context = build_exercise_context(
        user_data,
        personalization,
    )
    weekly_plan = build_weekly_plan(
        personalization
    )
    friendly_coach_message = build_friendly_coach_message(
        user_data,
        personalization,
        activity_replacements,
    )

    return {
        "classification": classification,
        "projected_weekend_screen_time": weekend_prediction,
        "cluster": cluster,
        "explanation": explanation,
        "recommendations": recommendations,
        "activity_replacements": activity_replacements,
        "friendly_coach_message": friendly_coach_message,
        "weekly_plan": weekly_plan,
        "exercise_context": exercise_context,
        "productive_digital": productive_digital,
        "ergonomic_guidance": build_ergonomic_guidance(),
        "balance_breakdown": build_balance_breakdown(
            user_data
        ),
        "percentiles": {
            "daily_screen_time_hours": percentile(
                "daily_screen_time_hours",
                user_data["daily_screen_time_hours"],
            ),
            "social_media_hours": percentile(
                "social_media_hours",
                user_data["social_media_hours"],
            ),
            "weekend_screen_time": percentile(
                "weekend_screen_time",
                user_data["weekend_screen_time"],
            ),
            "notifications_per_day": percentile(
                "notifications_per_day",
                user_data["notifications_per_day"],
            ),
        },
        "disclaimer": (
            "This is a machine-learning digital wellness aid, not a medical diagnosis. "
            "Model scores and percentiles are model- and dataset-relative."
        ),
    }
