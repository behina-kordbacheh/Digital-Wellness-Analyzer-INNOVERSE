# Digital Wellness Analyzer - Medal-Ready Final Submission

A local-first, AI-powered digital wellness web application built for an Innoverse 2026 competition submission.

## What the system does

The project combines multiple machine-learning and product components:

- Random Forest classification for lower-risk vs higher-risk digital usage patterns
- Tuned classification threshold selected from fixed 5-fold out-of-fold predictions
- Isotonic-calibrated Model Risk Score for the UI
- Random Forest regression for estimated weekend screen time
- K-Means clustering for user behavior segmentation
- SHAP explanations for individual predictions
- Dataset-relative percentile analysis
- Context-aware activity replacement recommendations
- Focus-software recommendations
- Local PDF report export
- Local SQLite history and trend analytics
- Recommendation Acceptance Rate tracking
- User Satisfaction Score tracking
- Manual Telegram summary sharing without a bot token
- HTML + CSS + JavaScript UI served by Flask

## Important scientific decisions

### Target leakage was removed

The `addiction_level` column is intentionally excluded from classification because it almost directly encodes `addicted_label` in this dataset. `transaction_id` and `user_id` are also excluded because they are identifiers rather than behavior features.

### Occupation is not an ML feature

Occupation, free time, main goal, device platform, preferred activity style, peak scrolling time, and social-media trigger are used only after the model prediction to personalize recommendations. They are not silently added to the classifier because the training dataset does not contain those features.

### No fake LSTM

The provided dataset is cross-sectional. It does not contain true chronological sequences for each user. Therefore, the project uses a supervised Random Forest regressor for the available screen-time prediction task instead of claiming an LSTM model without valid sequential training data.

### No cloud API

The final project uses:

- local joblib model files
- local SQLite history
- local PDF report generation
- manual Telegram share link

Automatic Telegram bot scheduling is intentionally not included because that would require an external Telegram Bot API/backend. The app instead shows the next check-in locally and places it in the exported PDF.

## Main files

```text
Digital_Wellness_Medal_Ready_Final/
|
|-- app.py
|-- wellness_engine.py
|-- train_models.py
|-- local_store.py
|-- report_generator.py
|-- pre_submission_check.py
|-- requirements.txt
|
|-- data/
|   `-- usage_data(2).csv
|
|-- models/
|   |-- digital_wellness_rf.joblib
|   |-- digital_wellness_isotonic.joblib
|   |-- weekend_screen_regressor.joblib
|   |-- cluster_scaler.joblib
|   |-- behavior_kmeans.joblib
|   |-- cluster_profiles.joblib
|   |-- wellness_reference_data.joblib
|   |-- decision_policy.json
|   `-- metrics.json
|
|-- templates/
|   `-- index.html
|
|-- static/
|   |-- style.css
|   `-- app.js
|
|-- reports/
|   `-- sample_judge_report.pdf
|
`-- instance/
    `-- wellness_history.db  (created locally at runtime)
```

## Quick run on Windows

Open PowerShell inside the project folder.

### 1. Install packages

```powershell
python -m pip install -r requirements.txt
```

### 2. Verify the submission

```powershell
python pre_submission_check.py
```

### 3. Run the application

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

The ZIP already includes trained model artifacts. You do not need to train again just to run the demo.

## Rebuild the models

If you intentionally want to retrain from the included competition dataset:

```powershell
python train_models.py
```

Then run:

```powershell
python app.py
```

## Evaluation summary

See `models/metrics.json` and `MODEL_CARD.md` for the exact evaluation protocol and scores.

## Judge-safe terminology

Use these phrases during the presentation:

- "Higher-risk digital usage pattern"
- "Lower-risk digital usage pattern"
- "Model Risk Score"
- "Dataset-relative percentile"
- "Personalized wellness recommendation"
- "Behavior segment"

Avoid claiming:

- medical diagnosis
- clinical probability
- guaranteed health outcome
- causal health effect from SHAP

## Code comments

All code comments in the submission are written in English.

## Video Presentation

Open:

```text
http://127.0.0.1:5000/video-demo
```

The page contains 8 full-screen video scenes. Use `VIDEO_PRESENTATION_SCRIPT.md`
for the 90-second English narration and `VIDEO_SHOT_LIST.md` for timing.

The main UI was redesigned for video recording:
- bright premium health-product style
- normal native browser scrolling
- no forced scroll JavaScript
- large readable report cards
- simplified input structure
- clear balance score and SHAP evidence


## Lifestyle Upgrade Features

This version adds:

- Exercise days per week and minutes per session.
- Multi-select weekly activities.
- Detailed study/work/entertainment/offline-social time.
- Optional seven-day plan generator.
- Purposeful digital study/work context score.
- Friendly coaching message in addition to formal recommendations.
- Private daily mood/focus journal stored in local SQLite.
- Anxiety, stress, sadness, happiness, focus, exercise minutes, and free-text reflection.
- Personal trend comparison between exercise and non-exercise check-ins.
- Ergonomic computer-use guidance.
- Evidence-conscious blue-light message: the app does not claim that special blue-light glasses protect users from harmful computer radiation.

### Important methodology note

Exercise, mood, occupation, activity preferences, and weekly-plan fields are not
silently injected into the trained Random Forest classifier because the original
training dataset does not contain those variables. They are used only for
post-model personalization, planning, descriptive context, and local progress tracking.


## Day/Night Theme Upgrade

The web app now includes a visible Day/Night theme toggle, localStorage persistence, subtle video-friendly animations, and native browser scrolling only. No JavaScript wheel/touch scroll interception is used.

## Presentation Timing

A 10-minute judge presentation script and deck are included in the final package. Recommended delivery: 8–10 slides, with a live app demo at minute 6.


## Focus Sound Space

See `FOCUS_SOUND_SPACE.md` for the browser-based focus and relaxation audio feature.

## Daily & Monthly Progress Tracking

This build includes a real local progress layer in addition to the trained ML system.

- Every completed analysis is saved to the local `analyses` table.
- One canonical `daily_snapshots` row is kept per profile per calendar day.
- Re-running the analyzer on the same day updates that day's snapshot instead of double-counting it.
- The **My Progress** dashboard shows recent daily points, 7-day averages, 30-day averages, and up to 90 days of trend charts.
- Once enough history exists, the UI compares the current 30-day window with the previous 30-day window for Model Risk Score, daily screen time, social-media time, and sleep.
- Progress data remains in local SQLite under `instance/wellness_history.db` and is not used to retrain or alter the validated classifier.

This prototype uses **manual daily check-ins**. Automatic phone telemetry would require platform/device APIs and is intentionally described as future integration rather than claimed as an existing feature.

### Optional judge-demo history

For a video or live judge demo, you can create clearly labeled synthetic history for the local `JudgeDemo` account:

```powershell
python seed_demo_progress.py
```

The script does **not** retrain any model. It scores each synthetic historical input with the already-saved deployment models, creates a presentation-only local account, intentionally skips several dates, and stores the results only in the local demo database. Do not present these seeded records as real user data.

### Why model accuracy is unchanged

The progress upgrade modifies only persistence, aggregation, and UI visualization. It does not change `train_models.py`, `wellness_engine.py`, the 12 classifier inputs, model artifacts, preprocessing, calibration, decision policy, or SHAP computation.

## Local Accounts & Missing-Day Tracking

This version adds persistent local user accounts without changing the trained ML models.

- Each user creates a unique username and password.
- Passwords are stored with salted PBKDF2-HMAC-SHA256 password hashing; raw passwords are never written to SQLite.
- A signed browser session stays valid for up to 30 days on the same device unless the user logs out.
- Analyses, daily snapshots, mood check-ins, challenge feedback, and progress are isolated by `user_id`.
- The 30-day consistency panel distinguishes **Completed** days from **No data entered** days.
- Missing days remain null/missing. They are never converted into zero screen time or zero risk.
- Weekly and monthly averages use only recorded days and show how many days contributed.
- 90-day charts use calendar spacing and break the line across missing dates instead of connecting through artificial zero values.

The account system is local to the project folder. It is not a cloud identity system. Deleting the local SQLite database deletes the local accounts and history.

### First run

1. Start the app with `python app.py`.
2. Open `http://127.0.0.1:5000`.
3. Create a local account with a username and password of at least 8 characters.
4. Complete an analysis. Today's daily snapshot is stored automatically.
5. Return later and sign in with the same account to restore the progress dashboard.

### Judge-demo seeded account

For presentation-only synthetic history:

```powershell
python seed_demo_progress.py
```

The script creates the local account `JudgeDemo` and prints its demo-only password. Several dates are intentionally skipped so judges can see that missing check-ins are represented honestly. The seeded history is synthetic and must not be described as real user data.
