# Media Analysis Project

Machine Learning / NLP project for analyzing media coverage of blockades in Serbia (Nov 2024 – Aug 2025).

## Project Structure

```text
media-analysis/
│
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
├── .gitignore               # Git ignored files
├── config.yaml              # Central project configuration
│
├── data/
│   ├── raw/                # Raw scraped articles (JSONL/CSV)
│   ├── interim/            # Partially cleaned / transformed data
│   ├── processed/          # Final datasets for modeling
│   └── external/           # External resources (keywords, source metadata, labels)
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_baseline_models.ipynb
│   ├── 03_topic_modeling.ipynb
│   └── 04_event_similarity.ipynb
│
├── src/
│   ├── scraping/
│   │   ├── __init__.py
│   │   ├── base_scraper.py         # Abstract scraper interface
│   │   ├── scraper_utils.py        # Shared scraping helpers
│   │   ├── n1_scraper.py
│   │   ├── kurir_scraper.py
│   │   └── ...
│   │
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── clean_text.py           # Text cleaning pipeline
│   │   ├── normalize.py            # Script normalization / metadata cleanup
│   │   ├── deduplicate.py          # Duplicate article detection
│   │   └── dataset_builder.py
│   │
│   ├── features/
│   │   ├── __init__.py
│   │   ├── tfidf.py
│   │   ├── embeddings.py
│   │   └── vectorization.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── baseline_models.py      # Logistic regression / SVM
│   │   ├── transformer_models.py   # BERTić / XLM-R
│   │   ├── evaluation.py
│   │   └── train.py
│   │
│   └── analysis/
│       ├── __init__.py
│       ├── topic_modeling.py
│       ├── event_similarity.py
│       └── narrative_analysis.py
│
├── scripts/
│   ├── scrape_articles.py
│   ├── clean_dataset.py
│   ├── build_features.py
│   ├── train_models.py
│   └── run_analysis.py
│
├── outputs/
│   ├── figures/            # Visualizations
│   ├── tables/             # Exported result tables
│   ├── models/             # Saved trained models
│   └── reports/            # Generated reports / summaries
│
└── tests/
    ├── test_scraping.py
    ├── test_preprocessing.py
    └── test_models.py
```

---

## Workflow

### 1. Data Collection
Scrape news articles from selected Serbian media portals.

Output:
- `data/raw/*.jsonl`

### 2. Data Cleaning & Preprocessing
Clean and normalize article text:
- remove HTML / boilerplate
- normalize Cyrillic / Latin script
- remove duplicates
- clean metadata

Output:
- `data/processed/articles_clean.csv`

### 3. Feature Engineering
Generate document representations:
- TF-IDF
- embeddings
- transformer tokenization

### 4. Modeling
Train classification models:
- Logistic Regression
- SVM
- Transformer-based models (BERTić / XLM-R)

### 5. Analysis
Perform:
- topic modeling
- event similarity analysis
- narrative comparison

### 6. Visualization & Reporting
Generate:
- figures
- tables
- model evaluation reports

---

## Development Principles

- `src/` contains reusable project logic
- `scripts/` contains executable pipeline entrypoints
- `notebooks/` are for experimentation only
- raw data is never edited manually
- processed data is reproducible from scripts

---

## Initial Dataset Schema

Each article should follow this structure:

```json
{
  "url": "...",
  "portal": "n1",
  "source_group": "opposition_leaning",
  "date": "2025-03-15",
  "title": "...",
  "text": "...",
  "author": "...",
  "scraped_at": "2026-05-21T14:00:00"
}
```
