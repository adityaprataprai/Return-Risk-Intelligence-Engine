import lightgbm as lgb
import numpy as np
from sklearn.metrics import roc_auc_score
import polars as pl

# Load data
train = pl.read_parquet("data/features/train_features.parquet")
test = pl.read_parquet("data/features/test_features.parquet")

# Define features and target (Assuming 'is_fraud' is the target)
exclude_cols = {
    "return_id",
    "transaction_id",
    "user_id",
    "timestamp",
    "request_time",
    "graph_last_updated_at",
    "is_fraud",
    "split",
}
features = [c for c in train.columns if c not in exclude_cols]

X_train, y_train = train[features].to_pandas(), train["is_fraud"].to_pandas()
X_test, y_test = test[features].to_pandas(), test["is_fraud"].to_pandas()

# Quick fit
model = lgb.LGBMClassifier(n_estimators=50, random_state=42, verbose=-1)
model.fit(X_train, y_train)

# Evaluate
probs = np.asarray(model.predict_proba(X_test))
preds = probs[:, 1]
auroc = roc_auc_score(y_test, preds)

print(f"Baseline AUROC: {auroc:.4f}")
if auroc >= 0.70:
    print("[PASS] Features have predictive power (AUROC >= 0.70)")
else:
    print("[FAIL] Model underperformed. Features may lack signal.")