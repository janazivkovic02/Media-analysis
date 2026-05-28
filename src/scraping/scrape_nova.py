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

from scraping import DATE_FROM, DATE_TO, HEADERS, MONTHS, OUT_DIR

# Scraper for Nova - https://nova.rs
BASE_URL = "https://nova.rs"
START_URLS = [
    "https://nova.rs/tag/studentske-blokade/",
    "https://nova.rs/tag/studentski-protesti/",
    "https://nova.rs/tag/protest-studenata/",
]

# Output directory specific for Nova articles
NOVA_OUT_DIR = OUT_DIR / "nova"
NOVA_OUT_DIR.mkdir(parents=True, exist_ok=True)


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


def parse_nova_date(text: str):
    """
    Examples:
    10. jan. 2026. 19:04
    5. apr. 2025.
    danas 12:33
    juče 18:10
    """
    text = clean_text(text).lower()

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


def parse_datetime_value(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def is_article_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc != urlparse(BASE_URL).netloc:
        return False

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return False

    ignored_first_parts = {
        "tag",
        "author",
        "page",
        "wp-content",
        "wp-json",
        "najnovije",
        "komentari",
        "impresum",
        "o-nama",
        "marketing",
        "pravila-koriscenja",
        "politika-privatnosti",
    }
    if parts[0] in ignored_first_parts:
        return False

    allowed_first_parts = {
        "vesti",
        "sport",
        "showbiz",
        "zabava",
        "magazin",
        "kultura",
        "biznis",
        "video",
        "kolumne",
    }

    return parts[0] in allowed_first_parts


def extract_article_links(soup: BeautifulSoup) -> list[str]:
    links = []
    seen = set()
    root = soup.find("main") or soup

    for a in root.find_all("a", href=True):
        url = normalize_url(a["href"])
        text = clean_text(a.get_text(" ", strip=True)).casefold()

        if text in {"sledeća", "sledece", "next", "najnovije"}:
            continue
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

        if "next" in rel or text in {"sledeća", "sledece", "next", ">"}:
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


def extract_json_ld_metadata(soup: BeautifulSoup) -> tuple[str | None, date | None]:
    author = None
    published_date = None

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue

            graph = item.get("@graph")
            if isinstance(graph, list):
                items.extend(graph)

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
        for attr in (
            {"property": "article:published_time"},
            {"name": "date"},
            {"name": "pubdate"},
        ):
            meta_date = soup.find("meta", attrs=attr)
            if meta_date and meta_date.get("content"):
                published_date = parse_datetime_value(meta_date["content"])
                if published_date:
                    break

    time_tag = soup.find("time")
    if time_tag and not published_date:
        published_date = parse_datetime_value(time_tag.get("datetime"))
        if not published_date:
            published_date = parse_nova_date(time_tag.get_text(" ", strip=True))

    if not author:
        author_label = soup.find(string=re.compile(r"\bautor\b", re.I))
        if author_label:
            next_link = author_label.find_next("a")
            if next_link:
                author = clean_text(next_link.get_text(" ", strip=True))
            else:
                parent_text = clean_text(author_label.parent.get_text(" ", strip=True))
                author = clean_text(re.sub(r"autor:?", "", parent_text, flags=re.I))

    if not published_date:
        title = soup.find("h1")
        search_root = title.find_all_next(string=True, limit=40) if title else soup.find_all(string=True)
        for text_node in search_root:
            parsed_date = parse_nova_date(str(text_node))
            if parsed_date:
                published_date = parsed_date
                break

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
            "Podeli vest",
            "Podeli",
            "Pročitajte još",
            "Procitajte još",
            "Pratite nas",
            "Oglas",
            "Najnovije",
            "Najčitanije",
            "Najcitanije",
            "Komentari",
            "Ostavi komentar",
            "Vaša e-mail adresa",
            "Nova.rs",
            "Preuzmite našu aplikaciju",
        ]

        if any(phrase.lower() in txt.lower() for phrase in skip_phrases):
            continue

        paragraphs.append(txt)

    text = "\n\n".join(paragraphs)

    if not title or not published_date or not text:
        return None

    return {
        "source": "Nova",
        "portal": "nova.rs",
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

    for path in NOVA_OUT_DIR.glob("*.json"):
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
    path = NOVA_OUT_DIR / filename

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

    print(f"Loaded {len(seen_urls)} already scraped Nova URLs")

    for start_url in START_URLS:
        total_saved += scrape_tag(start_url, seen_urls)

    print(f"\nDone. Saved {total_saved} new articles to {NOVA_OUT_DIR}")


if __name__ == "__main__":
    main()
