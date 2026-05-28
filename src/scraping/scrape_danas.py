from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraping import DATE_FROM, DATE_TO, OUT_DIR, HEADERS

# Scraper for Danas - https://www.danas.rs
BASE_URL = "https://www.danas.rs"
TAGS = [
    "studenti-u-blokadi",
    "studentske-blokade",
    "studentski-protest",
]
START_URLS = [f"{BASE_URL}/tag/{tag}/" for tag in TAGS]

# Output directory specific for Danas articles
DANAS_OUT_DIR = OUT_DIR / "danas"
DANAS_OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, url))
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}/"


def parse_danas_date(text: str):
    text = clean_text(text).lower()

    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\.", text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        return date(year, month, day)

    today = date.today()
    if re.search(r"\bdanas\b", text):
        return today
    if re.search(r"\bjuče\b|\bjuce\b", text):
        return today - timedelta(days=1)

    return None


def is_article_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc != urlparse(BASE_URL).netloc:
        return False

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 3:
        return False

    ignored_first_parts = {
        "tag",
        "author",
        "page",
        "wp-content",
        "wp-json",
        "komentari",
    }
    if parts[0] in ignored_first_parts:
        return False

    return True


def extract_article_links(soup: BeautifulSoup) -> list[str]:
    links = []
    seen = set()
    root = soup.find("main") or soup

    for heading in root.find_all(["h2", "h3"]):
        heading_text = clean_text(heading.get_text(" ", strip=True)).casefold()
        if heading_text in {"kretanje članaka", "najnovije", "najčitanije"}:
            break

        a = heading.find("a", href=True)
        if not a:
            continue

        url = normalize_url(a["href"])
        if not is_article_url(url) or url in seen:
            continue

        seen.add(url)
        links.append(url)

    return links


def get_page_number(url: str) -> int:
    match = re.search(r"/page/(\d+)/?", urlparse(url).path)
    return int(match.group(1)) if match else 1


def find_next_page(soup: BeautifulSoup, current_url: str):
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True)).casefold()
        rel = {value.casefold() for value in a.get("rel", [])}

        if "next" in rel or text in {"sledeća", "sledece", "next", ">" }:
            return normalize_url(a["href"])

    page_numbers = []
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        if text.isdigit():
            page_numbers.append((int(text), normalize_url(a["href"])))

    if page_numbers:
        current = soup.find("span", class_=re.compile(r"current", re.I))
        current_text = clean_text(current.get_text()) if current else ""
        current_num = int(current_text) if current_text.isdigit() else get_page_number(current_url)

        for page_num, url in sorted(page_numbers):
            if page_num == current_num + 1:
                return url

    return None


def extract_author_and_date(soup: BeautifulSoup):
    author = None
    published_date = None

    time_tag = soup.find("time")
    if time_tag:
        datetime_value = time_tag.get("datetime")
        if datetime_value:
            try:
                published_date = datetime.fromisoformat(datetime_value.replace("Z", "+00:00")).date()
            except ValueError:
                published_date = None
        if not published_date:
            published_date = parse_danas_date(time_tag.get_text(" ", strip=True))

    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = clean_text(meta_author["content"])

    if not author:
        title = soup.find("h1")
        if title:
            for element in title.find_all_next(string=True, limit=20):
                text = clean_text(str(element))
                if parse_danas_date(text):
                    parts = re.split(r"\d{1,2}\.\d{1,2}\.\d{4}\.|danas|juče|juce", text, maxsplit=1, flags=re.I)
                    author = clean_text(parts[0]) if parts and clean_text(parts[0]) else None
                    published_date = published_date or parse_danas_date(text)
                    break

    if not published_date:
        published_date = parse_danas_date(soup.get_text(" ", strip=True))

    return author, published_date


def extract_article(url: str, tag_page: str) -> dict | None:
    soup = get_soup(url)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None

    author, published_date = extract_author_and_date(soup)

    article = soup.find("article") or soup.find("main") or soup
    paragraphs = []

    for p in article.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))

        if len(txt) < 30:
            continue

        skip_phrases = [
            "Pratite nas",
            "Pretplatite se",
            "Komentari",
            "Ostali komentari",
            "Povezane vesti",
            "Najčitanije",
            "Najnovije",
            "Danas.rs",
            "Pridružite se",
        ]

        if any(phrase.lower() in txt.lower() for phrase in skip_phrases):
            continue

        paragraphs.append(txt)

    text = "\n\n".join(paragraphs)

    if not title or not published_date or not text:
        return None

    return {
        "source": "Danas",
        "portal": "danas.rs",
        "tag_page": tag_page,
        "url": url,
        "title": title,
        "author": author,
        "published_date": published_date.isoformat(),
        "text": text,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
    }


def make_filename(url: str) -> str:
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)
    return f"{slug}_{h}.json"


def load_existing_urls() -> set[str]:
    urls = set()

    for path in DANAS_OUT_DIR.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                article = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        url = article.get("url")
        if url:
            urls.add(normalize_url(url))

    return urls


def save_article(article: dict):
    filename = make_filename(article["url"])
    path = DANAS_OUT_DIR / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)


def scrape_tag(start_url: str, seen_urls: set[str]) -> int:
    current_url = start_url
    saved = 0
    page_num = 1

    while current_url:
        print(f"\n[TAG {start_url}] [PAGE {page_num}] {current_url}")
        soup = get_soup(current_url)

        article_links = extract_article_links(soup)
        print(f"Found {len(article_links)} candidate article links")

        page_dates = []

        for url in article_links:
            if url in seen_urls:
                print(f"SKIP DUPLICATE: {url}")
                continue

            seen_urls.add(url)

            try:
                article = extract_article(url, start_url)
            except Exception as e:
                print(f"ERROR: {url} -> {e}")
                continue

            time.sleep(1)

            if article is None:
                continue

            article_date = date.fromisoformat(article["published_date"])
            page_dates.append(article_date)

            if DATE_FROM <= article_date <= DATE_TO:
                save_article(article)
                saved += 1
                print(f"SAVED {article_date}: {article['title']}")
            else:
                print(f"SKIP  {article_date}: {article['title']}")

        if page_dates and max(page_dates) < DATE_FROM:
            print("Reached articles older than DATE_FROM. Stopping this tag.")
            break

        current_url = find_next_page(soup, current_url)
        page_num += 1

        time.sleep(2)

    return saved


def main():
    seen_urls = load_existing_urls()
    total_saved = 0

    print(f"Loaded {len(seen_urls)} already scraped Danas URLs")

    for start_url in START_URLS:
        total_saved += scrape_tag(start_url, seen_urls)

    print(f"\nDone. Saved {total_saved} new articles to {DANAS_OUT_DIR}")


if __name__ == "__main__":
    main()
