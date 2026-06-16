# Serbian Media Analysis: Student Blockades

This repository contains a Python pipeline for collecting and preparing Serbian news articles about student blockades and protests. The current implementation focuses on scraping selected Serbian media portals, building a unified article dataset, cleaning text for NLP, creating train/test splits, and generating feature representations for classification.

The project is designed as a Machine Learning / NLP project where the main modeling task is to classify articles by media source and later analyze differences in media coverage across portals.

## Project Goal

The goal of the project is to collect articles about student blockades in Serbia from several media portals and prepare them for text classification and media coverage analysis.

The current pipeline supports:

- scraping articles from multiple Serbian news portals;
- storing raw articles as JSON files;
- combining scraped articles into a single CSV dataset;
- cleaning text and removing leakage patterns;
- converting Cyrillic text to Latin script;
- creating train/test datasets;
- building TF-IDF and Embedić feature representations.

The scraping period is defined in `src/scraping/__init__.py`:

```python
DATE_FROM = date(2024, 12, 1)
DATE_TO = date(2025, 8, 1)
```

## Supported Portals

The implemented scrapers currently cover the following portals:

| Portal | Scraper file | Output folder |
|---|---|---|
| N1 | `src/scraping/scrape_n1.py` | `data/raw/n1/` |
| Nova | `src/scraping/scrape_nova.py` | `data/raw/nova/` |
| Danas | `src/scraping/scrape_danas.py` | `data/raw/danas/` |
| Politika | `src/scraping/scrape_politika.py` | `data/raw/politika/` |
| Blic | `src/scraping/scrape_blic.py` | `data/raw/blic/` |
| Kurir | `src/scraping/scrape_kurir.py` | `data/raw/kurir/` |

Each scraper follows portal-specific tag pages and extracts article links, titles, dates, article text, and available metadata.

## Repository Structure

```text
Media-analysis-main/
│
├── README.md
├── requirements.txt
├── pyproject.toml
├── .gitignore
│
├── data/
│   └── processed/
│       └── features/
│   ├── articles.csv
│   ├── articles_clean.csv
│   ├── train.csv
│   ├── test.csv
│   └── raw/
│       └── n1/
│       └── nova/
│       └── danas/
│       └── kurir/
│       └── blic/
│       └── politika/
│
├── notebooks/
│   └── 01_data_exploration.ipynb
│
├── scripts/
│   ├── scrape_articles.py
│   └── build_articles_dataset.py
│
└── src/
    ├── analysis/
    │   └── __init__.py
    │
    ├── features/
    │   └── __init__.py
    │   └── build_feature.py
    │
    ├── models/
    │   └── __init__.py
    │
    ├── preprocessing/
    │   ├── __init__.py
    │   ├── cleaning.py
    │   └── cyrilic_to_latin.py
    │
    └── scraping/
        ├── __init__.py
        ├── base_scraper.py
        ├── scrape_blic.py
        ├── scrape_danas.py
        ├── scrape_kurir.py
        ├── scrape_n1.py
        ├── scrape_nova.py
        └── scrape_politika.py
```

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows
```

Install the project dependencies:

```bash
pip install -r requirements.txt
```

For feature engineering and notebook work, additional packages may be needed:

```bash
pip install pandas numpy scipy scikit-learn sentence-transformers torch cyrtranslit
```

Because the project uses a `src/` layout, run scripts with `PYTHONPATH=src` if the package is not installed in editable mode:

```bash
PYTHONPATH=src python scripts/scrape_articles.py
```

Alternatively, install the project locally:

```bash
pip install -e .
```

## Pipeline Overview

The project currently follows this workflow:

```text
1. Scrape articles
   ↓
2. Save raw JSON files to data/raw/<portal>/
   ↓
3. Build one combined CSV dataset
   ↓
4. Explore, clean, normalize, and split data in notebook
   ↓
5. Build TF-IDF and Embedić features
   ↓
6. Use generated features for classification models
```

## 1. Scraping Articles

To scrape all supported portals sequentially:

```bash
PYTHONPATH=src python scripts/scrape_articles.py
```

To scrape only selected portals:

```bash
PYTHONPATH=src python scripts/scrape_articles.py --portals n1 nova danas
```

To run selected scrapers in parallel:

```bash
PYTHONPATH=src python scripts/scrape_articles.py --portals n1 nova danas --parallel
```

Available portal names are:

```text
blic, danas, kurir, n1, nova, politika
```

Raw articles are saved as individual JSON files inside:

```text
data/raw/<portal>/
```

For example:

```text
data/raw/n1/
data/raw/nova/
data/raw/danas/
```

## 2. Raw Article Format

Each raw article is stored as a JSON object. The exact fields can vary slightly depending on the portal, but the intended structure is:

```json
{
  "source": "N1",
  "portal": "n1info.rs",
  "tag_page": "https://n1info.rs/tag/blokade",
  "url": "https://n1info.rs/...",
  "title": "Article title",
  "author": "Author name or null",
  "published_date": "2025-07-02",
  "text": "Full article text",
  "scraped_at": "2026-06-15T18:00:00"
}
```

The most important fields for later modeling are:

- `source` — media source used as the classification label;
- `url` — unique article URL, used for duplicate removal;
- `title` — article headline;
- `published_date` — publication date;
- `text` — article body.

## 3. Building the Combined Dataset

After scraping, combine all raw JSON files into one CSV file:

```bash
python scripts/build_articles_dataset.py
```

This script:

- searches for all `.json` files inside `data/raw/`;
- extracts the most important article fields;
- normalizes basic whitespace;
- removes duplicate URLs;
- saves the combined dataset as `data/processed/articles.csv`.

The output CSV columns are:

```text
source;url;title;published_date;text
```

The CSV file is written with:

- separator: `;`
- encoding: `utf-8-sig`
- quoted fields

This format is useful for Serbian text because article bodies may contain commas, quotation marks, and special characters.

## 4. Data Exploration and Cleaning

The notebook `notebooks/01_data_exploration.ipynb` is used for exploratory data analysis

The notebook currently performs:

- loading `data/processed/articles.csv`;
- looking at dataset

The cleaning and train test split is done in `scrips/make_clean_dataset.py` and `scrips/train_test_split.py`

The preprocessing helpers are located in:

```text
src/preprocessing/cleaning.py
src/preprocessing/cyrilic_to_latin.py
```

### Leakage Cleaning

The function `clean_leakage_patterns` removes patterns that could reveal the portal or metadata instead of article content, such as:

- URLs;
- HTML tags;
- HTML entities;
- `Foto:`;
- `Izvor:`;
- `Prenosi:`;
- `Autor:`;
- `Piše:`;
- `Rubrika:`;
- `Tagovi:`.

This is important because the classification task should learn from journalistic text style and content, not from obvious portal-specific metadata.

### Train/Test Split

The script creates:

```text
data/processed/train.csv
data/processed/test.csv
```

The split is stratified by `source`, which means that each portal should be represented proportionally in both train and test sets.

## 5. Feature Engineering

Feature generation is implemented in:

```text
src/features/build_feature.py
```

Run it after `train.csv` and `test.csv` have been created:

```bash
PYTHONPATH=src python src/features/build_feature.py
```

The script expects the following input files:

```text
data/processed/train.csv
data/processed/test.csv
```

It expects these columns:

```text
source
full_text
```

The script builds two types of features.

### A. TF-IDF Features

TF-IDF is used as a sparse baseline representation. The current configuration uses:

- word-level features;
- unigrams and bigrams;
- `min_df=3`;
- `max_df=0.90`;
- `max_features=100000`;
- sublinear term frequency scaling.

Saved outputs:

```text
data/processed/features/tfidf_train.npz
data/processed/features/tfidf_test.npz
data/processed/features/tfidf_vectorizer.pkl
```

### B. Embedić Embeddings

Dense semantic embeddings are generated using:

```text
djovak/embedic-base
```

This model is suitable for Serbian and related South Slavic languages. The script encodes article text and saves normalized dense vectors.

Saved outputs:

```text
data/processed/features/embedic_train.npy
data/processed/features/embedic_test.npy
```

### Labels

The `source` column is encoded with `LabelEncoder`.

Saved outputs:

```text
data/processed/features/labels_train.npy
data/processed/features/labels_test.npy
data/processed/features/label_encoder.pkl
```

## Current Modeling Task

The current feature pipeline is prepared for a supervised classification task:

```text
Input: article full_text
Target label: source
```

In other words, the first modeling goal is to predict which portal published an article based on its text.

This can be used as a baseline for later media analysis, but the results should be interpreted carefully. A high classification score may mean that portals have distinct writing styles, but it may also indicate that the dataset still contains source-specific signals or topic imbalance.

## Important Notes

### Raw Data Should Not Be Edited Manually

Raw scraped files in `data/raw/` should be treated as immutable. If cleaning is needed, it should be done through scripts or notebooks and saved into `data/processed/`.

### Avoid Data Leakage

For portal classification, it is important to remove obvious source identifiers before modeling. Examples include:

- portal names inside text;
- URLs;
- author signatures that appear only on one portal;
- image credits;
- source attribution phrases;
- tags and categories;
- repeated boilerplate text.

Otherwise, the model may learn shortcuts instead of meaningful textual patterns.

### Notebook vs Scripts

The notebook is useful for exploration and checking data quality. Once the preprocessing choices are stable, the cleaning and train/test split steps should ideally be moved into scripts, for example:

```text
scripts/make_clean_data.py
scripts/train_test_split.py
```

This would make the pipeline more reproducible.

## Suggested Next Steps

Recommended improvements for the next stage of the project:

1. Move final cleaning logic from the notebook into a script.
2. Add `data/processed/.gitkeep` so the processed folder exists in the repository.
3. Add a script for train/test splitting.
4. Add baseline models such as Logistic Regression and Linear SVM.
5. Add evaluation metrics: accuracy, macro F1, confusion matrix, and per-class scores.
6. Check whether portal-specific leakage remains in `full_text`.
7. Add documentation for each scraper explaining which tag pages are used.
8. Add simple tests for URL normalization, date parsing, and article extraction.

## Reproducible Run Order

A typical full run should look like this:

```bash
# 1. Scrape articles
PYTHONPATH=src python scripts/scrape_articles.py

# 2. Build combined CSV
python scripts/build_articles_dataset.py

# 3. Open notebook and create cleaned train/test files
jupyter notebook notebooks/01_data_exploration.ipynb

# 4. Build TF-IDF and Embedić features
PYTHONPATH=src python src/features/build_feature.py
```

After these steps, the main modeling inputs are available in:

```text
data/processed/features/
```

## Status

The project currently contains working components for scraping, dataset building, preprocessing helpers, exploratory data cleaning, train/test split creation, and feature engineering. The modeling and analysis modules are prepared as folders but still need implementation.
