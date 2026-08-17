# Persistent Account & Progress Tracking Upgrade

## What changed

The application now links local longitudinal wellness history to an authenticated user account instead of an editable profile nickname.

### Storage design

- `users`: local usernames and salted PBKDF2-HMAC-SHA256 password hashes.
- `analyses`: completed analysis events, linked by `user_id`.
- `daily_snapshots`: one canonical behavior point per authenticated user per date.
- `mood_checkins`: private mood/focus reflections, linked by `user_id`.

A same-day re-analysis updates the existing daily snapshot. This prevents repeated clicks from inflating weekly or monthly statistics.

## Returning-user behavior

After a user signs back in:

- their historical charts and check-in calendar are restored;
- the most recent behavioral inputs are prefilled for convenience;
- the user is reminded to update those values for the current day before analyzing;
- their history stays isolated from other local accounts.

## Missing-data design

The interface distinguishes three calendar states:

1. **Completed** — a daily analysis exists.
2. **No data entered** — tracking had started, but no check-in exists for that date.
3. **Before tracking** — the account/history did not yet exist for that date.

Missing dates are never converted into zero screen time, zero risk, or zero sleep. Weekly and monthly averages use recorded days only. The 90-day chart breaks the line across missing dates.

## Progress UI

The **My Progress** panel includes:

- last check-in date
- 30-day check-in consistency
- 30-day completed/missing calendar
- latest Model Risk Score
- 7-day average screen time
- 30-day average social-media use
- 30-day average sleep
- 90-day Model Risk Score chart
- 90-day daily screen-time chart
- current 30 days vs previous 30 days comparison
- explicit last-7-calendar-day status table

## Scientific wording

The dashboard describes changes in model-estimated digital behavior. It does not claim that a lower score proves a medical or health improvement, and it does not infer causation from the trends.

## ML integrity

No classifier, regressor, clustering artifact, preprocessing pipeline, threshold, calibration logic, SHAP code, or training file was modified for this upgrade.
