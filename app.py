from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
import json
import os
import secrets
from urllib.parse import quote

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from local_store import (
    analysis_belongs_to_user,
    authenticate_user,
    create_user,
    get_history,
    get_local_metrics,
    get_latest_snapshot,
    get_user_by_id,
    get_period_analytics,
    get_progress_dashboard,
    get_mood_history,
    get_mood_insights,
    init_db,
    mark_challenge_completed,
    save_analysis,
    save_mood_checkin,
    save_satisfaction_score,
)
from report_generator import REPORTS_DIR, generate_pdf_report
from wellness_engine import full_analysis


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def _load_or_create_session_secret() -> str:
    """Persist a local session-signing key without hard-coding credentials."""

    environment_key = os.environ.get("DW_SESSION_SECRET", "").strip()
    if environment_key:
        return environment_key

    key_path = INSTANCE_DIR / ".session_secret"
    if key_path.exists():
        value = key_path.read_text(encoding="utf-8").strip()
        if value:
            return value

    value = secrets.token_hex(32)
    key_path.write_text(value, encoding="utf-8")
    return value


app = Flask(__name__)
app.secret_key = _load_or_create_session_secret()
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


MODEL_METRICS_PATH = BASE_DIR / "models" / "metrics.json"
GRID_SEARCH_PATH = BASE_DIR / "models" / "grid_search_results.json"


def _load_json_file(path: Path) -> dict:
    """Load optional local evaluation metadata for the judge-facing UI."""

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


MODEL_METRICS = _load_json_file(MODEL_METRICS_PATH)
GRID_SEARCH_RESULTS = _load_json_file(GRID_SEARCH_PATH)



# ----------------------------------------------------------------------
# Input helpers
# ----------------------------------------------------------------------

def _float(name: str, default: float = 0.0) -> float:
    """Read a numeric form value safely."""

    try:
        return float(request.form.get(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int = 0) -> int:
    """Read an integer form value safely."""

    try:
        return int(float(request.form.get(name, default)))
    except (TypeError, ValueError):
        return default


def _build_next_checkin(interval: str) -> str:
    """Convert a simple local reminder interval into a readable date/time."""

    day_map = {
        "Tomorrow": 1,
        "3 days": 3,
        "7 days": 7,
        "30 days": 30,
    }

    days = day_map.get(interval, 7)
    next_checkin = datetime.now() + timedelta(days=days)

    return next_checkin.strftime(
        "%Y-%m-%d %H:%M"
    )


def _build_telegram_share_url(
    profile_name: str,
    result: dict,
    next_checkin: str,
) -> str:
    """Build a manual Telegram share link without a bot token or cloud backend."""

    classification = result["classification"]
    score = (
        classification["calibrated_risk_score"]
        * 100.0
    )

    summary = (
        f"Digital Wellness Report - {profile_name}\n"
        f"Status: {classification['wellness_status']}\n"
        f"Model Risk Score: {score:.1f}%\n"
        f"Estimated weekend screen time: "
        f"{result['projected_weekend_screen_time']:.1f} h\n"
        f"Behavior cluster: {result['cluster']['cluster_id']}\n"
        f"Next check-in: {next_checkin}\n\n"
        "This is a machine-learning wellness aid, not a medical diagnosis."
    )

    return (
        "https://t.me/share/url?url=&text="
        + quote(summary)
    )


# ----------------------------------------------------------------------
# Local account authentication
# ----------------------------------------------------------------------

def _current_user() -> dict | None:
    user_id = session.get("user_id")
    if user_id is None:
        return None
    try:
        return get_user_by_id(int(user_id))
    except (TypeError, ValueError):
        return None


def login_required(view):
    """Require a local account before accessing private wellness history."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if _current_user() is None:
            session.clear()
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    """Sign into a persistent local-only wellness account."""

    init_db()
    if _current_user() is not None:
        return redirect(url_for("index"))

    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate_user(username, password)
        if user is None:
            error = "Incorrect username or password."
        else:
            session.clear()
            session["user_id"] = int(user["id"])
            session.permanent = True
            return redirect(url_for("index"))

    return render_template(
        "auth.html",
        mode="login",
        error=error,
        username=username,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    """Create a local account with a one-way password hash."""

    init_db()
    if _current_user() is not None:
        return redirect(url_for("index"))

    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            error = "Passwords do not match."
        else:
            ok, message, user_id = create_user(username, password)
            if not ok:
                error = message
            else:
                session.clear()
                session["user_id"] = int(user_id)
                session.permanent = True
                return redirect(url_for("index"))

    return render_template(
        "auth.html",
        mode="register",
        error=error,
        username=username,
    )


@app.post("/logout")
def logout():
    """End the browser session without deleting locally stored history."""

    session.clear()
    return redirect(url_for("login"))


# ----------------------------------------------------------------------
# Main page
# ----------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Render the analyzer form and the complete local AI report."""

    init_db()
    current_user = _current_user()
    user_id = int(current_user["id"])
    profile_name = str(current_user["username"])

    result = None
    analysis_id = None
    report_url = None
    telegram_share_url = None
    next_checkin = None

    form_values = {
        "profile_name": profile_name,
        "age": 24,
        "gender": "Female",
        "daily_screen_time_hours": 7.5,
        "social_media_hours": 3.0,
        "gaming_hours": 1.5,
        "work_study_hours": 4.0,
        "sleep_hours": 7.0,
        "notifications_per_day": 120,
        "app_opens_per_day": 90,
        "weekend_screen_time": 9.0,
        "stress_level": "Medium",
        "academic_work_impact": "No",
        "occupation": "Student",
        "available_time": "30 minutes",
        "goal": "Reduce social media",
        "activity_preference": "Mixed",
        "peak_usage_time": "Evening",
        "social_media_reason": "Habit",
        "device_platform": "Any",
        "checkin_interval": "7 days",
        "exercise_days_per_week": 3,
        "exercise_minutes_per_session": 30,
        "wants_weekly_plan": "Yes",
        "selected_activities": [
            "Study",
            "Exercise",
            "Entertainment",
            "Offline Social",
        ],
        "study_hours_per_day": 3.0,
        "work_hours_per_day": 0.0,
        "entertainment_hours_per_day": 1.5,
        "offline_social_minutes": 30,
        "digital_study_hours": 2.5,
        "digital_work_hours": 0.0,
    }

    latest_saved_inputs = get_latest_snapshot(user_id)
    if request.method == "GET" and latest_saved_inputs:
        form_values.update(
            {
                "age": latest_saved_inputs["age"],
                "gender": latest_saved_inputs["gender"],
                "daily_screen_time_hours": latest_saved_inputs["daily_screen_time"],
                "social_media_hours": latest_saved_inputs["social_media_hours"],
                "gaming_hours": latest_saved_inputs["gaming_hours"],
                "sleep_hours": latest_saved_inputs["sleep_hours"],
                "notifications_per_day": latest_saved_inputs["notifications_per_day"],
                "app_opens_per_day": latest_saved_inputs["app_opens_per_day"],
                "weekend_screen_time": latest_saved_inputs["weekend_screen_time"],
                "stress_level": latest_saved_inputs["stress_level"],
                "academic_work_impact": latest_saved_inputs["academic_work_impact"],
            }
        )

    if request.method == "POST":
        selected_activities = request.form.getlist(
            "selected_activities"
        )

        lifestyle_context = {
            "exercise_days_per_week": _int(
                "exercise_days_per_week", 3
            ),
            "exercise_minutes_per_session": _int(
                "exercise_minutes_per_session", 30
            ),
            "wants_weekly_plan": request.form.get(
                "wants_weekly_plan", "No"
            ),
            "selected_activities": selected_activities,
            "study_hours_per_day": _float(
                "study_hours_per_day", 0.0
            ),
            "work_hours_per_day": _float(
                "work_hours_per_day", 0.0
            ),
            "entertainment_hours_per_day": _float(
                "entertainment_hours_per_day", 0.0
            ),
            "offline_social_minutes": _int(
                "offline_social_minutes", 0
            ),
            "digital_study_hours": _float(
                "digital_study_hours", 0.0
            ),
            "digital_work_hours": _float(
                "digital_work_hours", 0.0
            ),
        }

        derived_work_study = (
            lifestyle_context["digital_study_hours"]
            + lifestyle_context["digital_work_hours"]
        )

        user_data = {
            "age": _int("age", 24),
            "gender": request.form.get(
                "gender",
                "Female",
            ),
            "daily_screen_time_hours": _float(
                "daily_screen_time_hours",
                7.5,
            ),
            "social_media_hours": _float(
                "social_media_hours",
                3.0,
            ),
            "gaming_hours": _float(
                "gaming_hours",
                1.5,
            ),
            "work_study_hours": derived_work_study,
            "sleep_hours": _float(
                "sleep_hours",
                7.0,
            ),
            "notifications_per_day": _int(
                "notifications_per_day",
                120,
            ),
            "app_opens_per_day": _int(
                "app_opens_per_day",
                90,
            ),
            "weekend_screen_time": _float(
                "weekend_screen_time",
                9.0,
            ),
            "stress_level": request.form.get(
                "stress_level",
                "Medium",
            ),
            "academic_work_impact": request.form.get(
                "academic_work_impact",
                "No",
            ),
        }

        personalization = {
            "occupation": request.form.get(
                "occupation",
                "Student",
            ),
            "available_time": request.form.get(
                "available_time",
                "30 minutes",
            ),
            "goal": request.form.get(
                "goal",
                "Reduce social media",
            ),
            "activity_preference": request.form.get(
                "activity_preference",
                "Mixed",
            ),
            "peak_usage_time": request.form.get(
                "peak_usage_time",
                "Evening",
            ),
            "social_media_reason": request.form.get(
                "social_media_reason",
                "Habit",
            ),
            "device_platform": request.form.get(
                "device_platform",
                "Any",
            ),
        }
        personalization.update(lifestyle_context)

        checkin_interval = request.form.get(
            "checkin_interval",
            "7 days",
        )

        form_values.update(user_data)
        form_values.update(personalization)
        form_values["selected_activities"] = selected_activities
        form_values["profile_name"] = profile_name
        form_values["checkin_interval"] = checkin_interval

        result = full_analysis(
            user_data,
            personalization,
        )

        next_checkin = _build_next_checkin(
            checkin_interval
        )

        result["next_checkin"] = next_checkin

        analysis_id = save_analysis(
            user_id=user_id,
            profile_name=profile_name,
            user_data=user_data,
            result=result,
            next_checkin=next_checkin,
        )

        report_filename = (
            f"digital_wellness_report_{analysis_id}.pdf"
        )
        report_path = (
            REPORTS_DIR / report_filename
        )

        generate_pdf_report(
            output_path=report_path,
            profile_name=profile_name,
            user_data=user_data,
            personalization=personalization,
            result=result,
            next_checkin=next_checkin,
        )

        report_url = (
            f"/reports/{report_filename}"
        )

        telegram_share_url = (
            _build_telegram_share_url(
                profile_name,
                result,
                next_checkin,
            )
        )

    active_profile = form_values[
        "profile_name"
    ]

    history = get_history(
        user_id,
        limit=30,
    )
    local_metrics = get_local_metrics(user_id)
    period_analytics = get_period_analytics(
        user_id,
        active_profile,
    )
    progress_dashboard = get_progress_dashboard(
        user_id,
        active_profile,
        days=90,
    )
    mood_history = get_mood_history(
        user_id,
        limit=14,
    )
    mood_insights = get_mood_insights(user_id)

    return render_template(
        "index.html",
        result=result,
        current_user=current_user,
        latest_saved_inputs=latest_saved_inputs,
        form=form_values,
        analysis_id=analysis_id,
        report_url=report_url,
        telegram_share_url=telegram_share_url,
        next_checkin=next_checkin,
        history=history,
        local_metrics=local_metrics,
        period_analytics=period_analytics,
        progress_dashboard=progress_dashboard,
        mood_history=mood_history,
        mood_insights=mood_insights,
        model_metrics=MODEL_METRICS,
        grid_search=GRID_SEARCH_RESULTS,
    )




# ----------------------------------------------------------------------
# Video presentation demo route
# ----------------------------------------------------------------------

@app.route("/video-demo")
def video_demo():
    """Render a deterministic demo result for competition video recording."""

    demo_user = {
        "age": 22,
        "gender": "Female",
        "daily_screen_time_hours": 9.2,
        "social_media_hours": 4.6,
        "gaming_hours": 1.4,
        "work_study_hours": 4.2,
        "sleep_hours": 6.3,
        "notifications_per_day": 210,
        "app_opens_per_day": 135,
        "weekend_screen_time": 12.1,
        "stress_level": "Medium",
        "academic_work_impact": "Yes",
    }

    demo_personalization = {
        "occupation": "Student",
        "available_time": "30 minutes",
        "goal": "Reduce social media",
        "activity_preference": "Physical",
        "peak_usage_time": "Evening",
        "social_media_reason": "Habit",
        "device_platform": "Any",
    }

    demo_result = full_analysis(
        demo_user,
        demo_personalization,
    )

    demo_result["next_checkin"] = "7 days"

    return render_template(
        "video_demo.html",
        result=demo_result,
        user=demo_user,
        personalization=demo_personalization,
    )


# ----------------------------------------------------------------------
# Local PDF and feedback endpoints
# ----------------------------------------------------------------------

@app.route("/reports/<path:filename>")
@login_required
def download_report(filename: str):
    """Download a report only when it belongs to the signed-in user."""

    prefix = "digital_wellness_report_"
    if not filename.startswith(prefix) or not filename.endswith(".pdf"):
        abort(404)

    analysis_text = filename[len(prefix):-4]
    if not analysis_text.isdigit():
        abort(404)

    user = _current_user()
    if not analysis_belongs_to_user(int(user["id"]), int(analysis_text)):
        abort(404)

    return send_from_directory(
        REPORTS_DIR,
        filename,
        as_attachment=True,
    )


@app.post("/api/challenge/<int:analysis_id>/complete")
@login_required
def complete_challenge(analysis_id: int):
    """Record challenge acceptance locally for evaluation metrics."""

    user = _current_user()
    mark_challenge_completed(
        int(user["id"]),
        analysis_id,
    )
    return jsonify(
        {
            "ok": True,
            "message": "Challenge completion saved locally.",
        }
    )


@app.post("/api/satisfaction/<int:analysis_id>/<int:score>")
@login_required
def satisfaction(analysis_id: int, score: int):
    """Store a local 1-5 recommendation satisfaction score."""

    user = _current_user()
    save_satisfaction_score(
        int(user["id"]),
        analysis_id,
        score,
    )
    return jsonify(
        {
            "ok": True,
            "score": max(1, min(score, 5)),
        }
    )


@app.get("/api/progress")
@login_required
def progress_api():
    """Return bounded local progress data for the authenticated account."""

    user = _current_user()
    return jsonify(
        get_progress_dashboard(
            int(user["id"]),
            str(user["username"]),
            days=90,
        )
    )


@app.post("/api/mood-checkin")
@login_required
def mood_checkin():
    """Save a private daily mood/focus reflection to the local database."""

    payload = request.get_json(silent=True) or {}

    user = _current_user()
    checkin_id = save_mood_checkin(
        user_id=int(user["id"]),
        profile_name=str(user["username"]),
        anxiety=int(payload.get("anxiety", 5)),
        stress=int(payload.get("stress", 5)),
        sadness=int(payload.get("sadness", 5)),
        happiness=int(payload.get("happiness", 5)),
        focus=int(payload.get("focus", 5)),
        exercise_minutes=int(payload.get("exercise_minutes", 0)),
        note=str(payload.get("note", "")),
    )

    insights = get_mood_insights(int(user["id"]))

    return jsonify(
        {
            "ok": True,
            "checkin_id": checkin_id,
            "insights": insights,
        }
    )


if __name__ == "__main__":
    app.run(
        debug=False,
        host="127.0.0.1",
        port=5000,
    )
