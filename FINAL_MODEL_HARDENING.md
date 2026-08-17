# Final Model Hardening

This release applies two judge-facing corrections without changing the validated feature set or adding target leakage.

## 1. Random Forest regularization

The classifier now uses:

- `n_estimators=300`
- `max_depth=20`
- `min_samples_leaf=2`
- `class_weight="balanced"`

The purpose is to reduce train-versus-validation overfitting while preserving out-of-fold performance.

Final fixed 5-fold OOF metrics at the locked `0.78` decision threshold:

- Accuracy: 0.9376
- Balanced Accuracy: 0.9554
- ROC-AUC: 0.9889
- Average Precision: 0.9956
- Macro F1: 0.9287
- Brier Score: 0.0359

Generalization check:

- Train balanced accuracy: 0.9577
- OOF balanced accuracy: 0.9554
- Gap: about 0.0023 (0.23 percentage points)

The earlier unrestricted forest had a much larger train-versus-OOF balanced-accuracy gap. The regularized model therefore provides a cleaner competition-facing generalization story without sacrificing the main validation metrics.

## 2. Weekend output wording

The dataset is cross-sectional rather than a true longitudinal time series. The regression output is therefore labeled **Estimated Weekend Screen Time**, not a forecast.

The Random Forest Regressor itself is retained, with the same holdout evaluation:

- MAE: 0.6311 hours
- RMSE: 0.7401 hours
- R2: 0.9265

Internal variable names are kept for backward compatibility, but all user-facing and judge-facing wording describes this output as an estimate from the current behavior profile.

## Evaluation integrity

- `addiction_level` remains excluded because it leaks the target.
- `transaction_id` and `user_id` remain excluded from classifier features.
- The decision threshold is locked at 0.78 rather than re-optimized on the final OOF predictions.
- The displayed Model Risk Score remains a model score, not a medical diagnosis or clinical probability.
