from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn import model_selection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_INPUT = PROCESSED_DIR / "articles_clean.csv"
DEFAULT_TRAIN_OUTPUT = PROCESSED_DIR / "train.csv"
DEFAULT_TEST_OUTPUT = PROCESSED_DIR / "test.csv"

RANDOM_STATE = 42
REQUIRED_COLUMNS = {"article_id", "source", "full_text"}


def create_train_test_split(
    input_path: Path = DEFAULT_INPUT,
    train_output: Path = DEFAULT_TRAIN_OUTPUT,
    test_output: Path = DEFAULT_TEST_OUTPUT,
    train_size: float = 0.8,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}\n"
            "First run: PYTHONPATH=src python scripts/make_clean_data.py"
        )

    df = pd.read_csv(input_path, sep=";", encoding="utf-8-sig")

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_path}: {sorted(missing_columns)}"
        )

    model_df = df[["article_id", "source", "full_text"]].copy()

    train_df, test_df = model_selection.train_test_split(
        model_df,
        train_size=train_size,
        stratify=model_df["source"],
        random_state=random_state,
    )

    train_output.parent.mkdir(parents=True, exist_ok=True)
    test_output.parent.mkdir(parents=True, exist_ok=True)

    train_df.to_csv(train_output, sep=";", index=False, encoding="utf-8-sig")
    test_df.to_csv(test_output, sep=";", index=False, encoding="utf-8-sig")

    print("Train/test split created")
    print(f"Input:  {input_path}")
    print(f"Train:  {train_output} ({len(train_df)} articles)")
    print(f"Test:   {test_output} ({len(test_df)} articles)")
    print(f"Train size ratio: {train_size}")
    print(f"Random state: {random_state}")

    print("\nTrain source distribution:")
    print(train_df["source"].value_counts(normalize=True).round(3).to_string())

    print("\nTest source distribution:")
    print(test_df["source"].value_counts(normalize=True).round(3).to_string())

    return train_df, test_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create stratified train/test split.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input articles_clean.csv path")
    parser.add_argument("--train-output", type=Path, default=DEFAULT_TRAIN_OUTPUT, help="Output train.csv path")
    parser.add_argument("--test-output", type=Path, default=DEFAULT_TEST_OUTPUT, help="Output test.csv path")
    parser.add_argument("--train-size", type=float, default=0.8, help="Train split size")
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE, help="Random seed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    create_train_test_split(
        input_path=args.input,
        train_output=args.train_output,
        test_output=args.test_output,
        train_size=args.train_size,
        random_state=args.random_state,
    )


if __name__ == "__main__":
    main()