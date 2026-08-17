# Upgrade Install Steps

This package is a complete project copy. It does not include `.git` metadata or private runtime account/history files.

## Safest upgrade path

1. Stop the Flask app if it is running.
2. Keep a backup of your current project folder.
3. Extract `Digital_Wellness_ACCOUNT_PROGRESS_Final.zip`.
4. Install/verify dependencies with `python -m pip install -r requirements.txt`.
5. Run `python progress_smoke_test.py`.
6. Run `python pre_submission_check.py`.
7. Run `python app.py` and open `http://127.0.0.1:5000`.
8. Create a local account or sign in to an existing one.
9. Complete an analysis. The app stores one daily snapshot for that account and restores the most recent behavioral values on a later visit.
10. Return on future days and sign in with the same username to see 7/30/90-day history, missing dates, and month comparison.
11. For competition video only, optionally run `python seed_demo_progress.py`. It creates clearly labeled synthetic presentation history and intentionally leaves several missing dates. Never describe seeded history as real user data.

## Files changed for this upgrade

- `local_store.py` — local users, salted password hashing, user-isolated storage, daily upsert, missing-aware analytics
- `app.py` — register/login/logout, persistent session, account-bound routes, restored inputs
- `templates/auth.html` — local account UI
- `templates/index.html` — signed-in account controls, persistent My Progress view, missing-day calendar
- `static/app.js` — missing values create chart gaps instead of zero values
- `static/style.css` — account and progress UI styling
- `README.md` — account and progress documentation
- `seed_demo_progress.py` — optional synthetic judge-demo account/history
- `progress_smoke_test.py` — isolated authentication/storage/analytics test

## ML integrity

This upgrade does not modify model training or inference. `train_models.py`, `wellness_engine.py`, model joblib files, decision policy, preprocessing, calibration, and model metrics remain unchanged.
