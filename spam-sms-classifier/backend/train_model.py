"""
train_model.py - SMS Spam Classifier Model Training Script
===========================================================
Trains three ML models (Naive Bayes, Logistic Regression, SVM)
on the SMS Spam Collection dataset and saves the best model.

Usage:
    python train_model.py

Output:
    - backend/model/spam_model.pkl     (best trained model)
    - backend/model/vectorizer.pkl     (TF-IDF vectorizer)
    - backend/model/model_results.json (evaluation metrics)
"""

import os
import sys
import subprocess

# ---------------------------------------------
# AUTO-FALLBACK: ensure 64-bit Python if 32-bit lacks packages
# ---------------------------------------------
def _check_and_reexec():
    try:
        import joblib
        import pandas
        import sklearn
        return
    except ImportError:
        pass

    if sys.platform == "win32":
        candidates = [
            ["py", "-V:3.13"],
            [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python313\python.exe")],
            [r"C:\Users\Asus\AppData\Local\Programs\Python\Python313\python.exe"],
        ]
        for cmd in candidates:
            try:
                test = subprocess.run(cmd + ["-c", "import sklearn, pandas"], capture_output=True)
                if test.returncode == 0:
                    ret = subprocess.run(cmd + [os.path.abspath(__file__)] + sys.argv[1:])
                    sys.exit(ret.returncode)
            except Exception:
                continue

_check_and_reexec()

import json
import re
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report
)

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------
# CONFIGURATION
# ---------------------------------------------
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH  = os.path.join(BASE_DIR, "..", "dataset", "spam.csv")
MODEL_DIR     = os.path.join(BASE_DIR, "model")
MODEL_PATH    = os.path.join(MODEL_DIR, "spam_model.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")
RESULTS_PATH  = os.path.join(MODEL_DIR, "model_results.json")
TEST_SIZE     = 0.20
RANDOM_STATE  = 42


# ─────────────────────────────────────────────
# STEP 1: LOAD DATASET
# ─────────────────────────────────────────────
def load_dataset(path: str) -> pd.DataFrame:
    """Load the SMS spam dataset from CSV."""
    print("\n[1/7] Loading dataset...")

    if not os.path.exists(path):
        print(f"\n  ERROR: Dataset not found at: {path}")
        print("  Please place spam.csv in the dataset/ folder.")
        print("  Download from: https://www.kaggle.com/datasets/uciml/sms-spam-collection-dataset")
        sys.exit(1)

    # Try to read dataset with multiple encodings
    df = None
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(path, encoding=enc, on_bad_lines="skip")
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    if df is None:
        # Fallback line-by-line reader
        import csv
        rows = []
        for enc in ["utf-8", "latin-1"]:
            try:
                with open(path, "r", encoding=enc, errors="ignore") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for r in reader:
                        if len(r) >= 2:
                            rows.append([r[0], " ".join(r[1:])])
                if rows:
                    df = pd.DataFrame(rows, columns=["v1", "v2"])
                    break
            except Exception:
                continue

    if df is None or len(df) == 0:
        print("  ERROR: Could not read dataset. Please ensure dataset/spam.csv is valid.")
        sys.exit(1)

    print(f"  Loaded {len(df)} rows, columns: {list(df.columns)}")

    # Auto-detect label and message columns
    label_col, msg_col = _detect_columns(df)
    print(f"  Detected label column: '{label_col}', message column: '{msg_col}'")

    df = df[[label_col, msg_col]].copy()
    df.columns = ["label", "message"]
    df.dropna(inplace=True)
    df.drop_duplicates(inplace=True)
    df.reset_index(drop=True, inplace=True)

    print(f"  After cleanup: {len(df)} records")
    print(f"  Distribution:\n{df['label'].value_counts().to_string()}")

    return df


def _detect_columns(df: pd.DataFrame):
    """Auto-detect label and message columns from various CSV formats."""
    col_lower = [c.lower().strip() for c in df.columns]

    # Common column naming patterns
    label_candidates = ["v1", "label", "class", "category", "type", "target"]
    msg_candidates   = ["v2", "message", "text", "sms", "content", "msg"]

    label_col = None
    msg_col   = None

    for cand in label_candidates:
        if cand in col_lower:
            label_col = df.columns[col_lower.index(cand)]
            break

    for cand in msg_candidates:
        if cand in col_lower:
            msg_col = df.columns[col_lower.index(cand)]
            break

    # Fallback: first two columns
    if label_col is None:
        label_col = df.columns[0]
    if msg_col is None:
        msg_col = df.columns[1]

    return label_col, msg_col


# ─────────────────────────────────────────────
# STEP 2: PREPROCESS
# ─────────────────────────────────────────────
def preprocess_text(text: str) -> str:
    """Basic NLP preprocessing pipeline."""
    text = str(text).lower()                      # lowercase
    text = re.sub(r"http\S+|www\S+", " url ", text)  # replace URLs
    text = re.sub(r"\d+", " num ", text)          # replace numbers
    text = re.sub(r"[^a-z\s]", " ", text)         # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()       # collapse whitespace
    return text


def preprocess_dataset(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[2/7] Preprocessing text...")
    df = df.copy()
    df["label"]          = df["label"].str.strip().str.lower()
    df["label_encoded"]  = df["label"].map({"spam": 1, "ham": 0})
    df.dropna(subset=["label_encoded"], inplace=True)
    df["label_encoded"]  = df["label_encoded"].astype(int)
    df["clean_message"]  = df["message"].apply(preprocess_text)
    print(f"  Spam: {df['label_encoded'].sum()}  |  Ham: {(df['label_encoded'] == 0).sum()}")
    return df


# ─────────────────────────────────────────────
# STEP 3: SPLIT
# ─────────────────────────────────────────────
def split_data(df: pd.DataFrame):
    print(f"\n[3/7] Splitting data ({int((1-TEST_SIZE)*100)}% train / {int(TEST_SIZE*100)}% test)...")
    X = df["clean_message"]
    y = df["label_encoded"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"  Train: {len(X_train)}  |  Test: {len(X_test)}")
    return X_train, X_test, y_train, y_test


# ─────────────────────────────────────────────
# STEP 4: VECTORIZE
# ─────────────────────────────────────────────
def vectorize(X_train, X_test):
    print("\n[4/7] Vectorizing with TF-IDF...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec  = vectorizer.transform(X_test)
    print(f"  Vocabulary size: {len(vectorizer.vocabulary_)}")
    return vectorizer, X_train_vec, X_test_vec


# ─────────────────────────────────────────────
# STEP 5: TRAIN MODELS
# ─────────────────────────────────────────────
def train_models(X_train, y_train):
    print("\n[5/7] Training models...")
    models = {
        "Multinomial Naive Bayes": MultinomialNB(alpha=0.1),
        "Logistic Regression": LogisticRegression(
            max_iter=1000, C=1.0, solver="lbfgs", random_state=RANDOM_STATE
        ),
        "Support Vector Machine": CalibratedClassifierCV(
            LinearSVC(max_iter=2000, C=1.0, random_state=RANDOM_STATE)
        ),
    }
    trained = {}
    for name, model in models.items():
        print(f"  Training {name}...")
        model.fit(X_train, y_train)
        trained[name] = model
    return trained


# ─────────────────────────────────────────────
# STEP 6: EVALUATE
# ─────────────────────────────────────────────
def evaluate_models(trained_models: dict, X_test, y_test) -> list:
    print("\n[6/7] Evaluating models...")
    results = []

    for name, model in trained_models.items():
        y_pred = model.predict(X_test)
        acc  = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec  = recall_score(y_test, y_pred, zero_division=0)
        f1   = f1_score(y_test, y_pred, zero_division=0)
        cm   = confusion_matrix(y_test, y_pred).tolist()

        result = {
            "model_name": name,
            "accuracy":   round(float(acc),  4),
            "precision":  round(float(prec), 4),
            "recall":     round(float(rec),  4),
            "f1_score":   round(float(f1),   4),
            "confusion_matrix": cm,
        }
        results.append(result)

        print(f"\n  -- {name} --")
        print(f"     Accuracy : {acc:.4f}")
        print(f"     Precision: {prec:.4f}")
        print(f"     Recall   : {rec:.4f}")
        print(f"     F1-Score : {f1:.4f}")
        print(classification_report(y_test, y_pred, target_names=["Ham", "Spam"]))

    return results


# ─────────────────────────────────────────────
# STEP 7: SELECT & SAVE BEST MODEL
# ─────────────────────────────────────────────
def save_best_model(trained_models: dict, results: list, vectorizer):
    print("\n[7/7] Selecting and saving best model...")

    best = max(results, key=lambda r: r["f1_score"])
    best_name  = best["model_name"]
    best_model = trained_models[best_name]

    print(f"\n  Best model: {best_name}")
    print(f"  F1-Score  : {best['f1_score']:.4f}")

    os.makedirs(MODEL_DIR, exist_ok=True)

    joblib.dump(best_model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    # Attach best_model flag and save results
    for r in results:
        r["is_best"] = (r["model_name"] == best_name)

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n  Model saved to   : {MODEL_PATH}")
    print(f"  Vectorizer saved : {VECTORIZER_PATH}")
    print(f"  Results saved    : {RESULTS_PATH}")

    return best_name


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  SMS SPAM CLASSIFIER - MODEL TRAINING")
    print("=" * 60)

    df               = load_dataset(DATASET_PATH)
    df               = preprocess_dataset(df)
    X_train, X_test, y_train, y_test = split_data(df)
    vectorizer, X_train_vec, X_test_vec = vectorize(X_train, X_test)
    trained_models   = train_models(X_train_vec, y_train)
    results          = evaluate_models(trained_models, X_test_vec, y_test)
    best_name        = save_best_model(trained_models, results, vectorizer)

    print("\n" + "=" * 60)
    print(f"  Training complete! Best model: {best_name}")
    print("  You can now start the Flask backend: python backend/app.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
