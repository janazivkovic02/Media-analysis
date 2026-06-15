"""
Feature Engineering for Serbian news classification.

Two representations are built and saved:
    A) TF-IDF  (sparse, fast baseline)
    B) Embedić embeddings  (dense, captures Serbian semantics)
       Model: djovak/embedic-base  (or -large)
       https://huggingface.co/djovak/embedic-large

Run:
    pip install scikit-learn sentence-transformers torch
    python src/features/build_features.py

Outputs (saved to data/processed/features/):
    tfidf_train.npz / tfidf_test.npz
    tfidf_vectorizer.pkl
    embedic_train.npy / embedic_test.npy
    labels_train.npy  / labels_test.npy
    label_encoder.pkl
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROC_DIR     = PROJECT_ROOT / "data" / "processed"
FEAT_DIR     = PROC_DIR / "features"
FEAT_DIR.mkdir(parents=True, exist_ok=True)

TEXT_COL = "full_text"
LABEL_COL = "source"



# ──────────────────────────────────────────────
# Load splits
# ──────────────────────────────────────────────

def load_split(name: str) -> pd.DataFrame:
    path = PROC_DIR / f"{name}.csv"
    return pd.read_csv(path, sep=";", encoding="utf-8-sig")


# ──────────────────────────────────────────────
# A) TF-IDF
# ──────────────────────────────────────────────

def build_labels(train_df: pd.DataFrame, test_df: pd.DataFrame):
    print("\n[C] Encoding labels...")

    le = LabelEncoder()

    y_train = le.fit_transform(train_df[LABEL_COL])
    y_test = le.transform(test_df[LABEL_COL])

    print(f"    Classes: {list(le.classes_)}")

    np.save(FEAT_DIR / "labels_train.npy", y_train)
    np.save(FEAT_DIR / "labels_test.npy", y_test)

    with open(FEAT_DIR / "label_encoder.pkl", "wb") as f:
        pickle.dump(le, f)

    print("    Saved: labels_train.npy, labels_test.npy, label_encoder.pkl")

    return y_train, y_test, le


def build_tfidf(train_df: pd.DataFrame, test_df: pd.DataFrame):
    print("\n[A] Building TF-IDF features...")

    train_texts = train_df[TEXT_COL]
    test_texts = test_df[TEXT_COL]

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.90,
        max_features=100_000,
        sublinear_tf=True,
        lowercase=False,
    )

    X_train = vectorizer.fit_transform(train_texts)
    X_test = vectorizer.transform(test_texts)

    print(f"    Vocabulary size: {len(vectorizer.vocabulary_)}")
    print(f"    Train shape: {X_train.shape}")
    print(f"    Test shape: {X_test.shape}")

    save_npz(FEAT_DIR / "tfidf_train.npz", X_train)
    save_npz(FEAT_DIR / "tfidf_test.npz", X_test)

    with open(FEAT_DIR / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)

    print("    Saved: tfidf_train.npz, tfidf_test.npz, tfidf_vectorizer.pkl")

    return X_train, X_test


def build_embedic(train_df: pd.DataFrame, test_df: pd.DataFrame):
    print("\n[B] Building Embedić embeddings...")
    print("    First run may download the model from HuggingFace.")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("djovak/embedic-base")

    def encode(df: pd.DataFrame, split_name: str):
        texts = (
            df[TEXT_COL]
            .fillna("")
            .astype(str)
            .str.slice(0, 3000)
            .tolist()
        )

        print(f"    Encoding {split_name}: {len(texts)} articles")

        embeddings = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        return embeddings

    E_train = encode(train_df, "train")
    E_test = encode(test_df, "test")

    np.save(FEAT_DIR / "embedic_train.npy", E_train)
    np.save(FEAT_DIR / "embedic_test.npy", E_test)

    print(f"    Embedding dim: {E_train.shape[1]}")
    print("    Saved: embedic_train.npy, embedic_test.npy")

    return E_train, E_test


def run():
    print("=" * 60)
    print("FEATURE ENGINEERING")
    print("=" * 60)

    train_df = load_split("train")
    test_df = load_split("test")

    print(f"Train size: {len(train_df)}")
    print(f"Test size: {len(test_df)}")

    build_labels(train_df, test_df)
    build_tfidf(train_df, test_df)
    build_embedic(train_df, test_df)

    print("\n" + "=" * 60)
    print("DONE - features saved to data/processed/features/")
    print("=" * 60)


if __name__ == "__main__":
    run()