# Phase 3: Model Training and Calibration

## Objective

Train and evaluate the ML model(s) using the offline feature dataset from Phase 2. Produce a calibrated LightGBM model and compare against XGBoost and logistic regression baseline. Save model artifact with version metadata.

## Scope

- Implement model training, calibration, and evaluation scripts.
- Use LightGBM as primary, XGBoost as benchmark, logistic regression as sanity check.
- Perform calibration on a separate validation set.
- Save trained models, calibration objects, feature schema, and metrics to `model_registry/`.

## Deliverables

- `src/models/__init__.py`
- `src/models/train.py`
- `src/models/calibrate.py`
- `src/models/evaluate.py`
- `src/models/registry.py`
- `scripts/train_model.py`
- `config/model_training.yaml`

## Technical Requirements

### 1. Model Training Configuration

`config/model_training.yaml`:

```yaml
model:
  type: lightgbm
  objective: binary
  metric: ["auc", "binary_logloss"]
  num_leaves: 63
  learning_rate: 0.05
  n_estimators: 500
  early_stopping_rounds: 50
  reg_alpha: 0.1
  reg_lambda: 0.1
  min_child_samples: 50
  subsample: 0.9
  colsample_bytree: 0.9
  random_state: 42

calibration:
  method: isotonic
  validation_split: temporal
  cv_folds: 5
```

### 2. Training Script

- Load `data/features/train_features.parquet` and `data/features/validation_features.parquet`.
- Separate features from target (`is_fraud` from hidden labels).
- For LightGBM:
  - Use `lgb.LGBMClassifier` with parameters from config.
  - Fit on train with early stopping using validation.
- For XGBoost:
  - Use `xgb.XGBClassifier` similar parameters.
- For logistic regression:
  - Use `sklearn.linear_model.LogisticRegression` as baseline.

### 3. Calibration

- Take the top model (LightGBM or XGBoost) and calibrate probabilities.
- Use `sklearn.calibration.CalibratedClassifierCV` with method `sigmoid` or `isotonic` on validation set.
- Save calibration object separately.

### 4. Evaluation Metrics

Compute on test set:
- AUROC
- AUPRC
- Precision, Recall, F1
- Recall at fixed FPR (e.g., 5%)
- Precision at top-K (e.g., top 10%)
- Brier score
- Reliability curve (plot and save)
- Scenario-wise recall (using hidden ground truth `true_scenario`)

### 5. Model Registry

Create `model_registry/return-risk/1.0.0/` containing:
- `model.txt` (LightGBM)
- `calibration.pkl`
- `feature_schema.json` (list of feature names in order)
- `feature_version.json`
- `training_config.json`
- `metrics.json`
- `metadata.json` (git commit hash, timestamp, training worlds)

Implement `src/models/registry.py` with functions to load/save model versions.

## Acceptance Criteria

- AUPRC > 0.50 on test set.
- Brier score < 0.25.
- Model artifact saved and can be loaded.
- Scenario-wise recall shows detection for all three fraud families.
- Calibration curve shows reasonable alignment.
- `scripts/train_model.py` runs end-to-end.
