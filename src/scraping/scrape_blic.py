from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraping import DATE_FROM, DATE_TO, HEADERS, MONTHS, OUT_DIR

# Scraper for Blic - https://www.blic.rs
BASE_URL = "https://www.blic.rs"
START_URLS = [
    "https://www.blic.rs/studentske-blokade",
    "https://www.blic.rs/blokade-studenata",
    "https://www.blic.rs/studenti-u-blokadi",
    "https://www.blic.rs/studentski-protesti",
]

# Output directory specific for Blic articles
BLIC_OUT_DIR = OUT_DIR / "blic"
BLIC_OUT_DIR.mkdir(parents=True, exist_ok=True)


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
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def normalize_page_url(url: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, url))
    query = urlencode(parse_qs(parsed.query), doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", query, ""))


def parse_datetime_value(value: str | None):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_blic_date(text: str):
    """
    Examples:
    14.08.2025
    14. avgust 2025. 22:03
    10. jan. 2025.
    danas 12:33
    juče 18:10
    """
    text = clean_text(text).lower()

    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        return date(year, month, day)

    match = re.search(r"(\d{1,2})\.\s*([a-zčćšđž]+)\.?\s*(\d{4})", text)
    if match:
        day = int(match.group(1))
        month_key = match.group(2)[:3]
        year = int(match.group(3))
        month = MONTHS.get(month_key)
        if month:
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
    if len(parts) < 4:
        return False

    ignored_first_parts = {
        "bbc",
        "najnovije-vesti",
        "o-nama",
        "pravila-i-uslovi-koriscenja-sajta",
        "svg-assets",
    }
    if parts[0] in ignored_first_parts:
        return False

    return bool(re.fullmatch(r"[a-z0-9]{7}", parts[-1]))


def extract_article_links(soup: BeautifulSoup) -> list[str]:
    links = []
    seen = set()
    roots = soup.select(".section__left--inner-left") or [soup.find("main") or soup]

    for root in roots:
        for article in root.select("article.news-box__item"):
            a = article.find("a", href=True)
            if not a:
                continue

            url = normalize_url(a["href"])
            if not is_article_url(url) or url in seen:
                continue

            seen.add(url)
            links.append(url)

    return links


def get_page_number(url: str) -> int:
    parsed = urlparse(url)
    value = parse_qs(parsed.query).get("strana", ["1"])[0]
    return int(value) if value.isdigit() else 1


def find_next_page(soup: BeautifulSoup, current_url: str):
    form = soup.find("form", id="pagination-next-form")
    next_input = form.find("input", attrs={"name": "strana"}) if form else None

    if next_input and next_input.get("value", "").isdigit():
        parsed = urlparse(current_url)
        query = parse_qs(parsed.query)
        query["strana"] = [next_input["value"]]
        return normalize_page_url(urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(query, doseq=True), "")))

    current_num = get_page_number(current_url)
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True)).casefold()
        if text in {"sledeća", "sledece", "next", ">"}:
            href = a["href"]
            if href == "#":
                continue
            return normalize_page_url(href)

    page_numbers = []
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        if text.isdigit():
            url = normalize_page_url(a["href"])
            if urlparse(url).netloc == urlparse(BASE_URL).netloc:
                page_numbers.append((int(text), url))

    for page_num, url in sorted(page_numbers):
        if page_num == current_num + 1:
            return url

    return None


def iter_json_ld_items(soup: BeautifulSoup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue

        items = data if isinstance(data, list) else [data]
        index = 0

        while index < len(items):
            item = items[index]
            index += 1

            if not isinstance(item, dict):
                continue

            graph = item.get("@graph")
            if isinstance(graph, list):
                items.extend(graph)

            yield item


def extract_json_ld_metadata(soup: BeautifulSoup) -> tuple[str | None, date | None]:
    author = None
    published_date = None

    for item in iter_json_ld_items(soup):
        item_type = item.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]

        if "NewsArticle" not in types and "Article" not in types:
            continue

        if not published_date:
            published_date = parse_datetime_value(item.get("datePublished"))

        if not author:
            author_data = item.get("author")
            if isinstance(author_data, dict):
                author = author_data.get("name")
            elif isinstance(author_data, list) and author_data:
                first_author = author_data[0]
                if isinstance(first_author, dict):
                    author = first_author.get("name")
                elif isinstance(first_author, str):
                    author = first_author
            elif isinstance(author_data, str):
                author = author_data

    return clean_text(author) if author else None, published_date


def extract_author_and_date(soup: BeautifulSoup):
    author, published_date = extract_json_ld_metadata(soup)

    if not author:
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = clean_text(meta_author["content"])

    if not published_date:
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date and meta_date.get("content"):
            published_date = parse_datetime_value(meta_date["content"])

    time_tag = soup.find("time")
    if time_tag and not published_date:
        published_date = parse_datetime_value(time_tag.get("datetime"))
        if not published_date:
            published_date = parse_blic_date(time_tag.get_text(" ", strip=True))

    if not author:
        author_tag = soup.select_one(".article__author-name")
        if author_tag:
            author = clean_text(author_tag.get_text(" ", strip=True))

    if not published_date:
        published_date = parse_blic_date(soup.get_text(" ", strip=True))

    return author, published_date


def extract_article(url: str, tag_page: str) -> dict | None:
    soup = get_soup(url)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None

    author, published_date = extract_author_and_date(soup)

    article = soup.select_one(".article__text") or soup.find("article") or soup.find("main") or soup

    for selector in (
        "aside",
        "script",
        "style",
        ".audio-player",
        ".article__author",
        ".article__images",
        ".article__tags",
        ".banner",
        ".news-aside",
        ".share-popup",
    ):
        for element in article.select(selector):
            element.decompose()

    paragraphs = []
    for p in article.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))

        if len(txt) < 30:
            continue

        skip_phrases = [
            "Dodaj Blic",
            "Slušaj vest",
            "Pročitajte još",
            "Procitajte još",
            "Podeli",
            "Pratite nas",
            "Oglas",
            "Najnovije",
            "Najčitanije",
            "Najcitanije",
            "Preporučujemo",
            "Komentari",
            "Pridružite se",
            "Blic Viber",
            "Blic WhatsApp",
            "Google News",
        ]

        if any(phrase.lower() in txt.lower() for phrase in skip_phrases):
            continue

        paragraphs.append(txt)

    text = "\n\n".join(paragraphs)

    if not title or not published_date or not text:
        return None

    return {
        "source": "Blic",
        "portal": "blic.rs",
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
    slug = url.rstrip("/").split("/")[-2]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)
    return f"{slug}_{h}.json"


def load_existing_urls() -> set[str]:
    urls = set()

    for path in BLIC_OUT_DIR.glob("*.json"):
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
    path = BLIC_OUT_DIR / filename

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

    print(f"Loaded {len(seen_urls)} already scraped Blic URLs")

    for start_url in START_URLS:
        total_saved += scrape_tag(start_url, seen_urls)

    print(f"\nDone. Saved {total_saved} new articles to {BLIC_OUT_DIR}")


if __name__ == "__main__":
    main()
