# Model Card

## Primary Classification Model

Random Forest Classifier

### Input features

1. age
2. gender
3. daily_screen_time_hours
4. social_media_hours
5. gaming_hours
6. work_study_hours
7. sleep_hours
8. notifications_per_day
9. app_opens_per_day
10. weekend_screen_time
11. stress_level
12. academic_work_impact

### Excluded leakage / identifier columns

- transaction_id
- user_id
- addiction_level

`addiction_level` is excluded because it almost deterministically reveals `addicted_label` in the provided dataset.

## Evaluation Protocol

- Fixed 5-fold StratifiedKFold
- shuffle=True
- evaluation random_state=2026
- Random Forest random_state=42
- Out-of-fold predicted probabilities
- Decision threshold locked at 0.78 from prior development; it is not re-optimized on the final OOF predictions

## Classification Results

From `models/metrics.json`:

- Decision threshold: 0.78
- Accuracy: 0.9376
- Balanced Accuracy: 0.9554
- Precision for class 1: 0.9992
- Recall for class 1: 0.9126
- Macro F1: 0.9287
- ROC-AUC: 0.9889
- Average Precision: 0.9956
- Brier Score: 0.0359

## Probability Display

An isotonic-calibrated Random Forest is used for the displayed **Model Risk Score**. The risk class itself is determined by the primary Random Forest probability and the locked 0.78 threshold.

The displayed score is not a medical probability.

## Regression Model

Random Forest Regressor estimates `weekend_screen_time` from current behavior features. The dataset is cross-sectional, so this output is presented as an estimate rather than a time-series forecast.

Fixed 80/20 holdout, random_state=2026:

- MAE: 0.6311 hours
- RMSE: 0.7401 hours
- R2: 0.9265

## Clustering

K-Means with 4 clusters is used for user behavior segmentation after StandardScaler preprocessing.

- Clusters: 4
- Silhouette score: 0.1069

The modest silhouette score is reported transparently. The clusters are used as descriptive behavior segments, not as diagnostic categories.

## Explainability

SHAP TreeExplainer explains the Random Forest classifier for each user. One-hot encoded categorical SHAP values are aggregated back to the original user-level feature names.

SHAP values explain model behavior. They do not prove causality or medical effects.


## Final Classifier Evaluation

The deployed Random Forest classifier is evaluated with fixed 5-fold stratified
out-of-fold predictions on the 7,500-row competition dataset after excluding
`transaction_id`, `user_id`, and the leakage-prone `addiction_level` field.

Current stored metrics:

- Accuracy: 0.9376
- Balanced Accuracy: 0.9554
- ROC-AUC: 0.9889
- Average Precision: 0.9956
- Positive-class Precision: 0.9992
- Positive-class Recall: 0.9126
- Macro F1: 0.9287
- Brier Score: 0.0359
- Locked decision threshold: 0.78

Balanced accuracy is emphasized over raw accuracy because the target distribution
is imbalanced.

### GridSearchCV verification

A separate 3-fold stratified `GridSearchCV` verification searched:

- `n_estimators`: 200, 300
- `max_depth`: None, 20
- `min_samples_leaf`: 1, 2, 4

Best setting:

- `n_estimators=300`
- `max_depth=20`
- `min_samples_leaf=4`
- Mean CV ROC-AUC: 0.98912

The gain over a baseline-like Random Forest was only about 0.00017 ROC-AUC.
This indicates that hyperparameter tuning contributes very little compared with
the underlying signal and leakage-safe feature design.

The GridSearchCV score is not the same evaluation as the final 5-fold OOF
metrics and should not be presented as if the numbers are directly interchangeable.

The deployed regularized model uses `max_depth=20` and `min_samples_leaf=2`. The
3-fold grid's pure ROC-AUC optimum used leaf size 4, but the difference across the
regularized settings was extremely small. Leaf size 2 was retained because the
fixed 5-fold OOF check preserved slightly stronger ROC-AUC/AP and Brier performance
while still reducing the train-vs-OOF balanced-accuracy gap to about 0.23 points.

### Regularization and generalization check

The final classifier uses `max_depth=20` and `min_samples_leaf=2` instead of fully
unrestricted trees. This reduced the train-vs-OOF balanced-accuracy gap from about
3.5 percentage points in the earlier unrestricted model to about 0.23 percentage
points, while preserving or slightly improving the main out-of-fold metrics.

Stored diagnostics for the final model:

- Train ROC-AUC: 1.0000 (rounded)
- OOF ROC-AUC: 0.9889
- Train balanced accuracy at threshold 0.78: 0.9577
- OOF balanced accuracy at threshold 0.78: 0.9554
- Balanced-accuracy generalization gap: about 0.0023

The 0.78 decision threshold is locked from prior development and is not
re-optimized on the final OOF probabilities. An external dataset would still be
required for a fully independent production validation.
