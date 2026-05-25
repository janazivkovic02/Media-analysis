from datetime import date
from pathlib import Path

#Period of interest for scraping - from December 1, 2024 to August 1, 2025
DATE_FROM = date(2024, 12, 1)
DATE_TO = date(2025, 8, 1)

# Directory for storing raw scraped data
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# User-Agent header to mimic a real browser and avoid blocking by websites
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "Chrome/120.0 Safari/537.36"
}

# Mapping of Serbian month abbreviations to month numbers
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "avg": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12
}
