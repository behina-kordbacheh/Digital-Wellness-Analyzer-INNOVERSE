# Digital Wellness Analyzer — 10-Minute Presentation Script

Language recommendation: slides in English, narration in English. Persian notes are for your practice.

## 0:00–0:45 — Opening
English: “Hello, my project is Digital Wellness Analyzer, an explainable AI system for healthier digital behavior. The system does not only detect risky screen habits. It explains the habit, predicts what may happen next, and gives the user a realistic action plan.”

## 0:45–1:45 — Problem
English: “Most digital wellness advice is too generic. It says ‘use your phone less,’ but screen time used for study is not the same as passive social media scrolling. Different users need different plans.”

## 1:45–2:45 — Solution
English: “The user enters digital habits and lifestyle context. The ML layer analyzes risk, future weekend usage and behavior segment. SHAP explains the decision. The recommendation layer gives activity replacements, a weekly plan and daily mood tracking.”

## 2:45–3:45 — Data & Ethics
English: “I avoided target leakage. User ID and transaction ID are not predictive behavior features. Addiction level is excluded because it leaks the target. New fields like occupation, mood and exercise are used only after prediction for personalization.”

## 3:45–5:00 — ML Architecture
English: “The system uses Random Forest classification, isotonic calibration, Random Forest regression, K-Means clustering and SHAP explainability.”

## 5:00–6:00 — Evaluation
English: “The final evaluation uses out-of-fold reporting. The classifier reaches about 0.988 ROC-AUC and about 0.955 balanced accuracy. The regression model estimates weekend screen time from the current behavior profile with about 0.63 hours MAE.”

## 6:00–7:15 — Live App Demo
Show: Day/Night toggle → inputs → Analyze → balance score → SHAP → weekly plan → mood check-in → PDF.
English: “Now I will show the app. The app produces a balance report, SHAP factors, percentile bars, a weekend estimate and an action plan.”

## 7:15–8:15 — Recommendation Engine
English: “Instead of only saying ‘reduce social media,’ the system suggests what the user can do instead: a walk, a study block, offline social time, or a focus tool based on their lifestyle.”

## 8:15–9:15 — Privacy, Reports, UX
English: “The app is local-first. SQLite stores one canonical behavior snapshot per day plus mood check-ins. The My Progress dashboard shows 7-day, 30-day and 90-day trends and month-to-month comparisons. It can also generate a PDF report and includes Day/Night mode, subtle animations and native scrolling.”

## 9:15–10:00 — Closing
English: “Digital Wellness Analyzer is not only a model. It is a full wellness product prototype: explainable, actionable and responsible. Thank you — I am ready for questions.”
