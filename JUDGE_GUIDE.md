# Judge Demo Guide

## 90-second demo flow

1. Enter a user profile and digital habits.
2. Choose occupation, available time, goal, trigger, platform, and next check-in.
3. Click **Analyze my digital wellness**.
4. Show the Digital Wellness Status and Model Risk Score.
5. Show the classification chart and time-balance chart.
6. Show SHAP factors explaining the model.
7. Show dataset-relative percentiles.
8. Show the Smart Activity Replacement section.
9. Show focus-software recommendations.
10. Download the local PDF report.
11. Show the next local check-in time.
12. Mark the challenge as completed and explain Recommendation Acceptance Rate.
13. Rate the recommendation to demonstrate the User Satisfaction Score metric.
14. Sign back into the same local account to show restored history, the missing-day calendar, and the local trend chart.

## Strong judge statements

> "We removed target leakage instead of using it to inflate accuracy."

> "The system separates prediction from personalization: occupation and goals personalize actions but are not fake classifier features."

> "SHAP explains why the Random Forest produced this result, while percentiles provide dataset context."

> "Instead of only telling the user to use social media less, the system recommends realistic replacement activities and optional focus software."

> "The application runs locally, stores history in SQLite, exports a PDF, and does not require a cloud API."

> "Because the dataset is not a true longitudinal sequence, we did not pretend to train an LSTM. We use a defensible regression target, while the product separately stores real local daily check-ins for 7-day, 30-day, and 90-day progress tracking."

## If a judge asks whether the user is healthy

Say:

> "The system reports a more balanced or needs-attention digital usage pattern. It is a wellness analytics tool, not a medical diagnostic system."


## If a judge asks: "How accurate is the model?"

Use this answer:

> "On fixed five-fold stratified out-of-fold evaluation, the classifier achieved
> 93.8% overall accuracy, 95.5% balanced accuracy, 0.9889 ROC-AUC, and 0.9956
> average precision. I emphasize balanced accuracy because the labels are imbalanced.
> I also removed the leakage-prone addiction_level column before training."


## If a judge asks: "Did the Random Forest overfit?"

Use this answer:

> "I checked the train-versus-out-of-fold gap and regularized the trees with a
> maximum depth of 20 and a minimum leaf size of 2. At the locked 0.78 decision
> threshold, train balanced accuracy is about 95.77% and out-of-fold balanced
> accuracy is about 95.54%, a gap of only about 0.23 percentage points. The OOF
> ROC-AUC remains about 0.9889."

## If a judge asks: "Did you use Grid Search?"

Use this answer:

> "Yes, I ran a separate GridSearchCV verification over Random Forest tree count,
> depth, and minimum leaf size. The best three-fold CV ROC-AUC was 0.9891 with
> 300 trees, max depth 20, and min leaf size 4. The gain over the baseline-like
> configuration was only about 0.00017 AUC, so tuning confirmed the model was
> already near a performance plateau. The final reported metrics come from the
> separate five-fold out-of-fold evaluation, not from the GridSearchCV score."

## Important honesty point

Do not call the displayed model risk score a medical probability or diagnosis.
The competition dataset is not an external clinical validation dataset.


## Persistent local account

> "Each user has a local username and salted password hash. Their analyses, mood check-ins, and progress are isolated by user ID. Missing dates are shown explicitly as no data entered and are never converted into artificial zeros."
