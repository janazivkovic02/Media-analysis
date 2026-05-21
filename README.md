Predlog strukture projekta:

media-analysis/
│
├── README.md
├── requirements.txt
├── .gitignore
├── config.yaml
│
├── data/
│   ├── raw/             
│   ├── processed/      
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_baseline_classification.ipynb
│   └── 03_topic_modeling.ipynb
│
├── src/
│   ├── scraping/
│   │   ├── __init__.py
│   │   ├── base_scraper.py
│   │   ├── n1_scraper.py
│   │   ├── kurir_scraper.py
│   │   └── scraper_utils.py
│   │
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── clean_text.py
│   │   ├── deduplicate.py
│   │   └── normalize.py
│   │
│   ├── features/
│   │   ├── __init__.py
│   │   ├── tfidf.py
│   │   └── embeddings.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── train_baseline.py
│   │   ├── evaluate.py
│   │   └── bert_model.py
│   │
│   └── analysis/
│       ├── __init__.py
│       ├── topic_modeling.py
│       └── event_similarity.py
│
├── scripts/
│   ├── scrape_articles.py
│   ├── clean_dataset.py
│   ├── train_baseline.py
│   └── run_topic_modeling.py
│
├── outputs/
│   ├── figures/
│   ├── tables/
│   └── models/
│
└── tests/
    └── test_clean_text.py
