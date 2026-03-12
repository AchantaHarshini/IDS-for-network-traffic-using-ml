import pandas as pd
import numpy as np
from io import StringIO
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import os

# Find latest CSV in uploads
folder = r'C:\Users\HARSHINI ACHANTA\Downloads\final_one\uploads'
files = [f for f in os.listdir(folder) if f.endswith('.csv')]
latest = max(files, key=lambda f: os.path.getmtime(os.path.join(folder, f)))
filepath = os.path.join(folder, latest)
print(f"Testing file: {filepath}")

# Step 1: Read CSV
print("\n--- Step 1: Reading CSV ---")
df = pd.read_csv(filepath, low_memory=False)
print(f"Columns: {len(df.columns)}")
if len(df.columns) == 1:
    print("Single column detected - stripping quotes...")
    rows = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            rows.append(line.strip().strip('"'))
    df = pd.read_csv(StringIO('\n'.join(rows)), low_memory=False)
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")

# Step 2: Find label column
print("\n--- Step 2: Finding label column ---")
CANDIDATES = [" Label", "Label", "label", "class", "Class", "attack_cat", "Attack Type", "attack_type"]
label_col = None
for c in CANDIDATES:
    if c in df.columns:
        label_col = c
        break
print(f"Label column: {label_col}")
print(f"Label values: {df[label_col].unique()[:10]}")

# Step 3: Preprocess
print("\n--- Step 3: Preprocessing ---")
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df.dropna(inplace=True)
print(f"After dropna: {df.shape}")

y_raw = df[label_col].astype(str).str.strip()
X = df.drop(columns=[label_col])
X = X.select_dtypes(include=[np.number])
y = (~y_raw.str.upper().isin(["BENIGN", "NORMAL", "BENIGN TRAFFIC"])).astype(int)
print(f"X shape: {X.shape}")
print(f"y distribution: {y.value_counts().to_dict()}")

# Step 4: Train test split
print("\n--- Step 4: Train/test split ---")
if len(X) > 300000:
    X, _, y, _ = train_test_split(X, y, train_size=300000, stratify=y, random_state=42)
    print(f"Subsampled to: {X.shape}")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
print(f"Train: {X_train.shape}, Test: {X_test.shape}")

# Step 5: Train model
print("\n--- Step 5: Training RandomForest ---")
clf = RandomForestClassifier(n_estimators=10, max_depth=10, n_jobs=-1, random_state=42)
clf.fit(X_train, y_train)
print("✅ Training complete!")
score = clf.score(X_test, y_test)
print(f"Accuracy: {score:.4f}")