import json
import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTICLES_CSV = PROCESSED_DIR / "articles.csv"
CSV_COLUMNS = ["source", "url", "title", "published_date", "text"]



def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item is not None)

    return " ".join(str(value).split())


def first_present(data, *keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def load_raw_articles(raw_dir):
    articles = []
    files = sorted(raw_dir.rglob("*.json"))
    print(f"Pronađeno JSON fajlova: {len(files)}")

    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                print(f"Preskačem fajl {file}: JSON nije objekat")
                continue

            articles.append({
                "source": first_present(data, "source", "portal") or file.parent.name,
                "url": first_present(data, "url", "link"),
                "title": clean_text(data.get("title")),
                "published_date": first_present(
                    data,
                    "published_date",
                    "published_data",
                    "publisded_data",
                    "date",
                    "published_at",
                ),
                "text": clean_text(data.get("text")),
            })

        except Exception as e:
            print(f"Greška u fajlu {file}: {e}")

    return articles


def remove_duplicate_urls(articles):
    seen_urls = set()
    unique_articles = []

    for article in articles:
        url = article["url"]
        if url and url in seen_urls:
            continue

        if url:
            seen_urls.add(url)
        
        unique_articles.append(article)

    return unique_articles


def main():
    articles = load_raw_articles(RAW_DIR)
    articles = remove_duplicate_urls(articles)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    with open(ARTICLES_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=CSV_COLUMNS,
            delimiter=";",
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(articles)

    print(f"Baza sačuvana u: {ARTICLES_CSV}")
    print(f"Broj članaka: {len(articles)}")

    for source, count in Counter(article["source"] for article in articles).most_common():
        print(f"{source}: {count}")


if __name__ == "__main__":
    main()