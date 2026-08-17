# Local Account + Missing-Day Progress Upgrade

## What changed

- Added local registration, login, logout, and persistent signed sessions.
- Added a `users` SQLite table.
- Added `user_id` ownership to analyses, daily snapshots, and mood check-ins.
- Passwords use salted PBKDF2-HMAC-SHA256 hashing; plaintext passwords are never stored.
- Returning users recover their own history after signing in.
- Added 30-day check-in consistency.
- Added explicit `No data entered` dates.
- Missing dates stay missing and are excluded from averages.
- 90-day chart lines break across missing dates instead of falling to zero.
- Added a last-check-in indicator and recent 7-calendar-day status table.

## ML integrity

This upgrade does not retrain or modify:

- `train_models.py`
- `wellness_engine.py`
- Random Forest classifier
- isotonic calibrated model
- weekend regressor
- K-Means artifacts
- preprocessing
- decision policy
- stored evaluation metrics

Authentication and longitudinal storage are post-model application layers.

## Privacy model

This is a local competition prototype, not a cloud account service. User data remains in `instance/wellness_history.db` on the computer running the app. The database and local session secret are ignored by Git.
