from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from preprocessing.cleaning import clean_leakage_patterns, make_fingerprint
from preprocessing.cyrilic_to_latin import convert_to_latin


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_INPUT = PROCESSED_DIR / "articles.csv"
DEFAULT_OUTPUT = PROCESSED_DIR / "articles_clean.csv"

REQUIRED_COLUMNS = {"source", "url", "title", "text"}


def normalize_text(series: pd.Series) -> pd.Series:
    """Convert to Latin script, lowercase, normalize whitespace, and remove leakage."""
    return (
        series.fillna("")
        .astype(str)
        .apply(convert_to_latin)
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .apply(clean_leakage_patterns)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def make_clean_dataset(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}\n"
            "First run: python scripts/build_articles_dataset.py"
        )

    df = pd.read_csv(input_path, sep=";", encoding="utf-8-sig")

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_path}: {sorted(missing_columns)}"
        )

    start_count = len(df)

    # Same logic as the notebook: title + article body are used as the modeling text.
    df["full_text"] = df["title"].fillna("") + " " + df["text"].fillna("")
    df["full_text"] = normalize_text(df["full_text"])

    # Remove exact URL duplicates first.
    before_url_dedup = len(df)
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    removed_url_duplicates = before_url_dedup - len(df)

    # Remove near duplicates using a simple text fingerprint.
    df["fingerprint"] = df["full_text"].apply(make_fingerprint)
    before_fingerprint_dedup = len(df)
    df = df.drop_duplicates(subset=["fingerprint"]).reset_index(drop=True)
    removed_fingerprint_duplicates = before_fingerprint_dedup - len(df)

    df["article_id"] = range(1, len(df) + 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, sep=";", index=False, encoding="utf-8-sig")

    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean combined Serbian media article dataset.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input articles.csv path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output articles_clean.csv path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    make_clean_dataset(args.input, args.output)


if __name__ == "__main__":
    main()