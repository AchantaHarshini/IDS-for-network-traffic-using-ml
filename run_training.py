"""
run_training.py - Run this directly to train and save the model.
Place in final_one folder and run: python run_training.py
"""
import pandas as pd
import numpy as np
import joblib
import json
from io import StringIO
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score,
                             recall_score, f1_score,
                             confusion_matrix, roc_curve, auc)

CSV_PATH  = r"uploads\clean_data.csv"
MODEL_OUT = r"backend\ids_model.pkl"
RESULT_OUT = r"backend\eval_result.json"

print("📂 Loading CSV...")
df = pd.read_csv(CSV_PATH, low_memory=False)
if len(df.columns) == 1:
    print("⚠️  Single-column CSV — stripping quotes...")
    rows = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            rows.append(line.strip().strip('"'))
    df = pd.read_csv(StringIO('\n'.join(rows)), low_memory=False)

print(f"✅ Loaded: {df.shape[0]} rows, {df.shape[1]} cols")
print(f"   Last column: {df.columns[-1]}")

LABEL_COL = df.columns[-1]  # 'Attack Type'
NORMAL_LABELS = {"BENIGN", "NORMAL", "NORMAL TRAFFIC", "BENIGN TRAFFIC"}

df.replace([np.inf, -np.inf], np.nan, inplace=True)
df.dropna(inplace=True)

y_raw = df[LABEL_COL].astype(str).str.strip()
X = df.drop(columns=[LABEL_COL]).select_dtypes(include=[np.number])
y = (~y_raw.str.upper().isin(NORMAL_LABELS)).astype(int)

print(f"   Classes: {y.value_counts().to_dict()}")

if len(X) > 300_000:
    X, _, y, y_raw_s = train_test_split(X, y, train_size=300_000, stratify=y, random_state=42)
    y_raw = y_raw.iloc[y_raw_s.index] if hasattr(y_raw_s, 'index') else y_raw
    print(f"   Subsampled to {len(X)} rows")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42)

print("🤖 Training RandomForest (this takes 2-5 min)...")
clf = RandomForestClassifier(n_estimators=100, max_depth=20,
                              n_jobs=-1, random_state=42,
                              class_weight="balanced")
clf.fit(X_train, y_train)
print("✅ Training complete!")

y_pred   = clf.predict(X_test)
y_scores = clf.predict_proba(X_test)[:, 1]

acc  = round(accuracy_score(y_test, y_pred), 4)
prec = round(precision_score(y_test, y_pred, zero_division=0), 4)
rec  = round(recall_score(y_test, y_pred, zero_division=0), 4)
f1   = round(f1_score(y_test, y_pred, zero_division=0), 4)
print(f"   Accuracy={acc}  Precision={prec}  Recall={rec}  F1={f1}")

cm = confusion_matrix(y_test, y_pred)
if cm.shape == (1, 1):
    tn, fp, fn, tp = (int(cm[0,0]),0,0,0) if y_test.iloc[0]==0 else (0,0,0,int(cm[0,0]))
else:
    tn, fp, fn, tp = cm.ravel()

fpr_arr, tpr_arr, _ = roc_curve(y_test, y_scores)
roc_auc = round(auc(fpr_arr, tpr_arr), 4)

importances = clf.feature_importances_
top_idx = np.argsort(importances)[::-1][:10]
feature_cols = list(X.columns)
feature_importance = [
    {"feature": feature_cols[i], "importance": round(float(importances[i]), 4)}
    for i in top_idx
]

# Full dataset attack breakdown
X_full = df.drop(columns=[LABEL_COL]).select_dtypes(include=[np.number])
y_raw_full = df[LABEL_COL].astype(str).str.strip()
y_pred_full = clf.predict(X_full)
attack_mask = y_pred_full == 1
attack_labels = y_raw_full[attack_mask]
attack_type_counts = attack_labels.value_counts().to_dict()

result = {
    "total_records": len(df),
    "attacks_detected": int(attack_mask.sum()),
    "normal_detected": int((~attack_mask).sum()),
    "attack_types": attack_type_counts,
    "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    "roc": {"fpr": fpr_arr.tolist(), "tpr": tpr_arr.tolist(), "auc": roc_auc},
    "feature_importance": feature_importance,
    "metrics": {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1},
}

joblib.dump(clf, MODEL_OUT)
with open(RESULT_OUT, 'w') as f:
    json.dump(result, f)

print(f"✅ Model saved → {MODEL_OUT}")
print(f"✅ Results saved → {RESULT_OUT}")
print(f"   Attacks: {result['attacks_detected']}  Normal: {result['normal_detected']}")