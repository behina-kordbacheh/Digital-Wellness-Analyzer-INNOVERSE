from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path



BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DATABASE_PATH = Path(
    os.environ.get("DW_DATABASE_PATH", str(INSTANCE_DIR / "wellness_history.db"))
)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def _connect():
    """Open and always close the local SQLite connection safely."""

    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
    finally:
        connection.close()


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    """Add a backward-compatible column when upgrading an older local DB."""

    if column_name not in _table_columns(connection, table_name):
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )


def init_db() -> None:
    """Create local account/history tables without changing ML artifacts."""

    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                profile_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                next_checkin TEXT,
                risk_class INTEGER NOT NULL,
                risk_score REAL NOT NULL,
                daily_screen_time REAL NOT NULL,
                social_media_hours REAL NOT NULL,
                gaming_hours REAL NOT NULL,
                work_study_hours REAL NOT NULL,
                sleep_hours REAL NOT NULL,
                weekend_screen_time REAL NOT NULL,
                projected_weekend REAL NOT NULL,
                cluster_id INTEGER NOT NULL,
                challenge_completed INTEGER NOT NULL DEFAULT 0,
                satisfaction_score INTEGER,
                result_json TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mood_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                profile_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                anxiety INTEGER NOT NULL,
                stress INTEGER NOT NULL,
                sadness INTEGER NOT NULL,
                happiness INTEGER NOT NULL,
                focus INTEGER NOT NULL,
                exercise_minutes INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                profile_name TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                daily_screen_time REAL NOT NULL,
                social_media_hours REAL NOT NULL,
                gaming_hours REAL NOT NULL,
                work_study_hours REAL NOT NULL,
                sleep_hours REAL NOT NULL,
                notifications_per_day INTEGER NOT NULL,
                app_opens_per_day INTEGER NOT NULL,
                weekend_screen_time REAL NOT NULL,
                stress_level TEXT,
                academic_work_impact TEXT,
                risk_class INTEGER NOT NULL,
                risk_score REAL NOT NULL,
                wellness_status TEXT,
                projected_weekend REAL,
                cluster_id INTEGER,
                top_factors_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                UNIQUE(profile_name, snapshot_date),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # Upgrade databases created by earlier project versions.
        _ensure_column(connection, "analyses", "user_id", "INTEGER")
        _ensure_column(connection, "mood_checkins", "user_id", "INTEGER")
        _ensure_column(connection, "daily_snapshots", "user_id", "INTEGER")

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_daily_user_date
            ON daily_snapshots(user_id, snapshot_date)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analysis_user_created
            ON analyses(user_id, created_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mood_user_created
            ON mood_checkins(user_id, created_at)
            """
        )
        connection.commit()


def _normalize_username(username: str) -> str:
    return username.strip()


def _hash_password(password: str) -> str:
    """Hash a password with salted PBKDF2-HMAC-SHA256."""

    iterations = 310_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return "$".join(
        [
            "pbkdf2_sha256",
            str(iterations),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a PBKDF2 password hash using constant-time comparison."""

    try:
        algorithm, iteration_text, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def create_user(username: str, password: str) -> tuple[bool, str, int | None]:
    """Create a local account using a one-way password hash."""

    init_db()
    clean_username = _normalize_username(username)

    if not 3 <= len(clean_username) <= 30:
        return False, "Username must be 3 to 30 characters.", None
    if not all(char.isalnum() or char in "_-" for char in clean_username):
        return False, "Username can use letters, numbers, underscore, and hyphen only.", None
    if len(password) < 8:
        return False, "Password must be at least 8 characters.", None
    if len(password) > 128:
        return False, "Password is too long.", None

    password_hash = _hash_password(password)
    created_at = datetime.now().isoformat(timespec="seconds")

    try:
        with _connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, password_hash, created_at, last_login_at)
                VALUES (?, ?, ?, ?)
                """,
                (clean_username, password_hash, created_at, created_at),
            )
            connection.commit()
            return True, "Account created.", int(cursor.lastrowid)
    except sqlite3.IntegrityError:
        return False, "That username already exists.", None


def authenticate_user(username: str, password: str) -> dict | None:
    """Verify local credentials without exposing the stored password hash."""

    init_db()
    clean_username = _normalize_username(username)

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash, created_at, last_login_at
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (clean_username,),
        ).fetchone()

        if row is None or not _verify_password(password, str(row["password_hash"])):
            return None

        now_text = datetime.now().isoformat(timespec="seconds")
        connection.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (now_text, int(row["id"])),
        )
        connection.commit()

    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "created_at": str(row["created_at"]),
        "last_login_at": now_text,
    }


def get_user_by_id(user_id: int) -> dict | None:
    """Return public account fields for a valid local user id."""

    init_db()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, username, created_at, last_login_at
            FROM users
            WHERE id = ?
            """,
            (int(user_id),),
        ).fetchone()

    return dict(row) if row is not None else None


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(int(value), upper))


def save_mood_checkin(
    user_id: int,
    profile_name: str,
    anxiety: int,
    stress: int,
    sadness: int,
    happiness: int,
    focus: int,
    exercise_minutes: int,
    note: str,
) -> int:
    """Save one private daily reflection to the current local account."""

    init_db()

    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO mood_checkins (
                user_id, profile_name, created_at, anxiety, stress, sadness,
                happiness, focus, exercise_minutes, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                profile_name.strip(),
                datetime.now().isoformat(timespec="seconds"),
                _clamp(anxiety, 1, 10),
                _clamp(stress, 1, 10),
                _clamp(sadness, 1, 10),
                _clamp(happiness, 1, 10),
                _clamp(focus, 1, 10),
                max(0, int(exercise_minutes)),
                note.strip()[:4000],
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def get_mood_history(user_id: int, limit: int = 30) -> list[dict]:
    """Return recent mood/focus check-ins for the authenticated user."""

    init_db()
    safe_limit = max(1, min(int(limit), 365))

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                id, created_at, anxiety, stress, sadness,
                happiness, focus, exercise_minutes, note
            FROM mood_checkins
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(user_id), safe_limit),
        ).fetchall()

    history = [dict(row) for row in rows]
    history.reverse()
    return history


def get_mood_insights(user_id: int) -> dict:
    """Summarize observed mood/focus patterns without causal claims."""

    history = get_mood_history(user_id, limit=60)

    if not history:
        return {
            "count": 0,
            "latest": None,
            "focus_change": None,
            "happiness_change": None,
            "exercise_day_focus": None,
            "non_exercise_day_focus": None,
            "exercise_day_happiness": None,
            "non_exercise_day_happiness": None,
            "note": "Add daily check-ins to see your own mood and focus trend over time.",
        }

    latest = history[-1]
    previous = history[-2] if len(history) >= 2 else None
    exercise_days = [row for row in history if int(row["exercise_minutes"] or 0) > 0]
    non_exercise_days = [row for row in history if int(row["exercise_minutes"] or 0) == 0]

    def average(rows: list[dict], key: str):
        if not rows:
            return None
        return round(sum(float(row[key]) for row in rows) / len(rows), 1)

    return {
        "count": len(history),
        "latest": latest,
        "focus_change": int(latest["focus"]) - int(previous["focus"]) if previous else None,
        "happiness_change": int(latest["happiness"]) - int(previous["happiness"]) if previous else None,
        "exercise_day_focus": average(exercise_days, "focus"),
        "non_exercise_day_focus": average(non_exercise_days, "focus"),
        "exercise_day_happiness": average(exercise_days, "happiness"),
        "non_exercise_day_happiness": average(non_exercise_days, "happiness"),
        "note": (
            "Differences between exercise and non-exercise check-ins are personal "
            "observations from your own entries and do not prove causation."
        ),
    }


def _upsert_daily_snapshot(
    connection: sqlite3.Connection,
    user_id: int,
    profile_name: str,
    user_data: dict,
    result: dict,
    snapshot_date: str | None = None,
) -> None:
    """Keep one canonical behavior snapshot per account per calendar day."""

    snapshot_date = snapshot_date or date.today().isoformat()
    now_text = datetime.now().isoformat(timespec="seconds")
    explanation = result.get("explanation", [])

    # New accounts use their unique username as profile_name. The legacy
    # UNIQUE(profile_name, snapshot_date) constraint therefore remains safe.
    connection.execute(
        """
        INSERT INTO daily_snapshots (
            user_id, profile_name, snapshot_date, updated_at, age, gender,
            daily_screen_time, social_media_hours, gaming_hours,
            work_study_hours, sleep_hours, notifications_per_day,
            app_opens_per_day, weekend_screen_time, stress_level,
            academic_work_impact, risk_class, risk_score, wellness_status,
            projected_weekend, cluster_id, top_factors_json, result_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_name, snapshot_date) DO UPDATE SET
            user_id = excluded.user_id,
            updated_at = excluded.updated_at,
            age = excluded.age,
            gender = excluded.gender,
            daily_screen_time = excluded.daily_screen_time,
            social_media_hours = excluded.social_media_hours,
            gaming_hours = excluded.gaming_hours,
            work_study_hours = excluded.work_study_hours,
            sleep_hours = excluded.sleep_hours,
            notifications_per_day = excluded.notifications_per_day,
            app_opens_per_day = excluded.app_opens_per_day,
            weekend_screen_time = excluded.weekend_screen_time,
            stress_level = excluded.stress_level,
            academic_work_impact = excluded.academic_work_impact,
            risk_class = excluded.risk_class,
            risk_score = excluded.risk_score,
            wellness_status = excluded.wellness_status,
            projected_weekend = excluded.projected_weekend,
            cluster_id = excluded.cluster_id,
            top_factors_json = excluded.top_factors_json,
            result_json = excluded.result_json
        """,
        (
            int(user_id),
            profile_name.strip(),
            snapshot_date,
            now_text,
            int(user_data.get("age", 0)),
            str(user_data.get("gender", "")),
            float(user_data["daily_screen_time_hours"]),
            float(user_data["social_media_hours"]),
            float(user_data["gaming_hours"]),
            float(user_data["work_study_hours"]),
            float(user_data["sleep_hours"]),
            int(user_data["notifications_per_day"]),
            int(user_data["app_opens_per_day"]),
            float(user_data["weekend_screen_time"]),
            str(user_data.get("stress_level", "")),
            str(user_data.get("academic_work_impact", "")),
            int(result["classification"]["risk_class"]),
            float(result["classification"]["calibrated_risk_score"]),
            str(result["classification"].get("wellness_status", "")),
            float(result.get("projected_weekend_screen_time", 0.0)),
            int(result.get("cluster", {}).get("cluster_id", -1)),
            json.dumps(explanation[:5], ensure_ascii=True),
            json.dumps(result, ensure_ascii=True),
        ),
    )


def save_analysis(
    user_id: int,
    profile_name: str,
    user_data: dict,
    result: dict,
    next_checkin: str,
) -> int:
    """Persist an analysis event and update today's account snapshot."""

    init_db()
    clean_profile = profile_name.strip()

    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO analyses (
                user_id, profile_name, created_at, next_checkin, risk_class,
                risk_score, daily_screen_time, social_media_hours,
                gaming_hours, work_study_hours, sleep_hours,
                weekend_screen_time, projected_weekend, cluster_id,
                result_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                clean_profile,
                datetime.now().isoformat(timespec="seconds"),
                next_checkin,
                int(result["classification"]["risk_class"]),
                float(result["classification"]["calibrated_risk_score"]),
                float(user_data["daily_screen_time_hours"]),
                float(user_data["social_media_hours"]),
                float(user_data["gaming_hours"]),
                float(user_data["work_study_hours"]),
                float(user_data["sleep_hours"]),
                float(user_data["weekend_screen_time"]),
                float(result["projected_weekend_screen_time"]),
                int(result["cluster"]["cluster_id"]),
                json.dumps(result, ensure_ascii=True),
            ),
        )

        # Repeated analyses on the same day update one daily point instead
        # of artificially inflating weekly or monthly progress statistics.
        _upsert_daily_snapshot(
            connection,
            int(user_id),
            clean_profile,
            user_data,
            result,
        )
        connection.commit()
        return int(cursor.lastrowid)


def save_demo_snapshot(
    user_id: int,
    profile_name: str,
    snapshot_date: str,
    user_data: dict,
    result: dict,
) -> None:
    """Store an explicitly synthetic daily snapshot for judge-demo preparation."""

    init_db()
    with _connect() as connection:
        _upsert_daily_snapshot(
            connection,
            int(user_id),
            profile_name.strip(),
            user_data,
            result,
            snapshot_date=snapshot_date,
        )
        connection.commit()


def analysis_belongs_to_user(user_id: int, analysis_id: int) -> bool:
    """Check ownership before exposing a generated per-analysis artifact."""

    init_db()
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM analyses WHERE id = ? AND user_id = ?",
            (int(analysis_id), int(user_id)),
        ).fetchone()
    return row is not None


def mark_challenge_completed(user_id: int, analysis_id: int) -> bool:
    """Record challenge completion only for the authenticated user's analysis."""

    init_db()
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE analyses
            SET challenge_completed = 1
            WHERE id = ? AND user_id = ?
            """,
            (int(analysis_id), int(user_id)),
        )
        connection.commit()
        return cursor.rowcount > 0


def save_satisfaction_score(user_id: int, analysis_id: int, score: int) -> bool:
    """Store a local 1-5 satisfaction score for the current user's analysis."""

    init_db()
    score = _clamp(score, 1, 5)
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE analyses
            SET satisfaction_score = ?
            WHERE id = ? AND user_id = ?
            """,
            (score, int(analysis_id), int(user_id)),
        )
        connection.commit()
        return cursor.rowcount > 0


def get_history(user_id: int, limit: int = 30) -> list[dict]:
    """Return recent analysis events for the authenticated local account."""

    init_db()
    safe_limit = max(1, min(int(limit), 365))

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                id, created_at, risk_score, daily_screen_time,
                social_media_hours, weekend_screen_time,
                projected_weekend, challenge_completed,
                satisfaction_score
            FROM analyses
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(user_id), safe_limit),
        ).fetchall()

    history = [dict(row) for row in rows]
    history.reverse()
    return history


def get_latest_snapshot(user_id: int) -> dict | None:
    """Return the most recent saved behavior inputs for form restoration."""

    init_db()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT
                snapshot_date, age, gender, daily_screen_time,
                social_media_hours, gaming_hours, work_study_hours,
                sleep_hours, notifications_per_day, app_opens_per_day,
                weekend_screen_time, stress_level, academic_work_impact
            FROM daily_snapshots
            WHERE user_id = ?
            ORDER BY snapshot_date DESC, updated_at DESC
            LIMIT 1
            """,
            (int(user_id),),
        ).fetchone()

    return dict(row) if row is not None else None


def get_daily_history(user_id: int, days: int = 90) -> list[dict]:
    """Return recorded daily points, bounded to avoid oversized payloads."""

    init_db()
    safe_days = max(1, min(int(days), 365))
    cutoff = (date.today() - timedelta(days=safe_days - 1)).isoformat()

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                snapshot_date, updated_at, risk_class, risk_score,
                wellness_status, daily_screen_time, social_media_hours,
                gaming_hours, work_study_hours, sleep_hours,
                notifications_per_day, app_opens_per_day,
                weekend_screen_time, projected_weekend, cluster_id
            FROM daily_snapshots
            WHERE user_id = ? AND snapshot_date >= ?
            ORDER BY snapshot_date ASC
            """,
            (int(user_id), cutoff),
        ).fetchall()

    return [dict(row) for row in rows]


def get_local_metrics(user_id: int) -> dict:
    """Calculate local recommendation acceptance and satisfaction metrics."""

    init_db()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(challenge_completed) AS completed,
                AVG(satisfaction_score) AS satisfaction
            FROM analyses
            WHERE user_id = ?
            """,
            (int(user_id),),
        ).fetchone()

    total = int(row["total"] or 0)
    completed = int(row["completed"] or 0)
    acceptance_rate = completed / total * 100.0 if total else 0.0

    return {
        "analysis_count": total,
        "recommendation_acceptance_rate": round(acceptance_rate, 1),
        "average_satisfaction": (
            round(float(row["satisfaction"]), 2)
            if row["satisfaction"] is not None
            else None
        ),
    }


def _average(rows: list[dict], key: str, scale: float = 1.0, digits: int = 2):
    if not rows:
        return None
    return round(sum(float(row[key]) for row in rows) / len(rows) * scale, digits)


def _period_summary(rows: list[dict]) -> dict:
    return {
        "count": len(rows),
        "average_risk": _average(rows, "risk_score", scale=100.0, digits=1),
        "average_daily_screen": _average(rows, "daily_screen_time"),
        "average_social_media": _average(rows, "social_media_hours"),
        "average_sleep": _average(rows, "sleep_hours"),
        "average_weekend_screen": _average(rows, "weekend_screen_time"),
    }


def _metric_change(current, previous, unit: str, digits: int = 1) -> dict:
    if current is None or previous is None:
        return {
            "current": current,
            "previous": previous,
            "delta": None,
            "percent": None,
            "unit": unit,
            "direction": "flat",
        }

    delta = round(float(current) - float(previous), digits)
    percent = None
    if abs(float(previous)) > 1e-9:
        percent = round(delta / float(previous) * 100.0, 1)

    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "percent": percent,
        "unit": unit,
        "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
    }


def get_progress_dashboard(
    user_id: int,
    profile_name: str,
    days: int = 90,
) -> dict:
    """Build missing-aware daily, weekly, monthly, and 90-day progress data."""

    safe_days = max(30, min(int(days), 365))
    history = get_daily_history(user_id, days=safe_days)
    today = date.today()
    history_by_date = {row["snapshot_date"]: row for row in history}

    def rows_since(days_back: int) -> list[dict]:
        cutoff = (today - timedelta(days=days_back - 1)).isoformat()
        return [row for row in history if row["snapshot_date"] >= cutoff]

    current_30_start = today - timedelta(days=29)
    previous_30_start = current_30_start - timedelta(days=30)
    previous_30_end = current_30_start - timedelta(days=1)

    current_30 = [
        row for row in history
        if current_30_start.isoformat() <= row["snapshot_date"] <= today.isoformat()
    ]
    previous_30 = [
        row for row in history
        if previous_30_start.isoformat() <= row["snapshot_date"] <= previous_30_end.isoformat()
    ]

    current_summary = _period_summary(current_30)
    previous_summary = _period_summary(previous_30)

    comparison = {
        "risk": _metric_change(
            current_summary["average_risk"],
            previous_summary["average_risk"],
            "points",
        ),
        "screen": _metric_change(
            current_summary["average_daily_screen"],
            previous_summary["average_daily_screen"],
            "h/day",
        ),
        "social": _metric_change(
            current_summary["average_social_media"],
            previous_summary["average_social_media"],
            "h/day",
        ),
        "sleep": _metric_change(
            current_summary["average_sleep"],
            previous_summary["average_sleep"],
            "h/night",
        ),
    }

    latest = history[-1] if history else None
    previous = history[-2] if len(history) >= 2 else None
    days_since_last = None
    if latest:
        days_since_last = (today - date.fromisoformat(latest["snapshot_date"])).days

    account = get_user_by_id(user_id)
    account_created_date = (
        date.fromisoformat(str(account["created_at"])[:10])
        if account and account.get("created_at")
        else today
    )
    first_record_date = date.fromisoformat(history[0]["snapshot_date"]) if history else None
    tracking_start = (
        min(account_created_date, first_record_date)
        if first_record_date is not None
        else account_created_date
    )

    # A fixed calendar timeline keeps missing days visible. Null values are
    # intentional and the front end draws gaps instead of converting them to 0.
    timeline = []
    for offset in range(safe_days - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_text = day.isoformat()
        row = history_by_date.get(day_text)
        eligible = day >= tracking_start
        if row is not None:
            status = "Completed"
        elif eligible:
            status = "No data entered"
        else:
            status = "Not tracking yet"

        timeline.append(
            {
                "date": day_text,
                "eligible": eligible,
                "recorded": row is not None,
                "status": status,
                "risk": round(float(row["risk_score"]) * 100.0, 1) if row else None,
                "screen": round(float(row["daily_screen_time"]), 2) if row else None,
                "social": round(float(row["social_media_hours"]), 2) if row else None,
                "sleep": round(float(row["sleep_hours"]), 2) if row else None,
            }
        )

    checkin_calendar = timeline[-30:]
    eligible_30 = [item for item in checkin_calendar if item["eligible"]]
    completed_30 = sum(1 for item in eligible_30 if item["recorded"])
    missing_30 = sum(1 for item in eligible_30 if not item["recorded"])
    consistency_30 = (
        round(completed_30 / len(eligible_30) * 100.0, 1)
        if eligible_30
        else 0.0
    )
    missing_dates_30 = [
        item["date"]
        for item in eligible_30
        if not item["recorded"]
    ]

    return {
        "profile_name": profile_name,
        "total_records": len(history),
        "first_date": history[0]["snapshot_date"] if history else None,
        "latest_date": history[-1]["snapshot_date"] if history else None,
        "latest": latest,
        "previous": previous,
        "days_since_last": days_since_last,
        "daily": _period_summary(rows_since(1)),
        "weekly": _period_summary(rows_since(7)),
        "monthly": _period_summary(rows_since(30)),
        "current_30": current_summary,
        "previous_30": previous_summary,
        "comparison": comparison,
        "timeline": timeline,
        "recorded_timeline": [item for item in timeline if item["recorded"]],
        "checkin_calendar": checkin_calendar,
        "tracking_start": tracking_start.isoformat(),
        "eligible_30": len(eligible_30),
        "completed_30": completed_30,
        "missing_30": missing_30,
        "consistency_30": consistency_30,
        "missing_dates_30": missing_dates_30,
        "has_month_comparison": bool(current_30 and previous_30),
        "tracking_note": (
            "One behavior snapshot is stored per authenticated account per calendar day. "
            "Repeating an analysis on the same day updates that day's point instead of double-counting it."
        ),
        "missing_note": (
            "A missing check-in stays missing. It is never converted to zero screen time, "
            "so absent data cannot artificially improve or worsen averages."
        ),
        "science_note": (
            "Trends describe changes in model-estimated digital behavior. "
            "They are not medical outcomes and do not establish causation."
        ),
    }


def get_period_analytics(user_id: int, profile_name: str) -> dict:
    """Backward-compatible period summary used by the main template."""

    dashboard = get_progress_dashboard(user_id, profile_name, days=90)
    return {
        "total_records": dashboard["total_records"],
        "daily": dashboard["daily"],
        "weekly": dashboard["weekly"],
        "monthly": dashboard["monthly"],
        "Today": dashboard["daily"],
        "7 days": dashboard["weekly"],
        "30 days": dashboard["monthly"],
    }
