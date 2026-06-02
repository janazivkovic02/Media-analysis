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

# Scraper for Politika - https://www.politika.rs
BASE_URL = "https://www.politika.rs"
START_URLS = [
    "https://www.politika.rs/scc/tags/articles/353/blokada",
    "https://www.politika.rs/scc/tags/articles/8109/blokaderi",
    "https://www.politika.rs/scc/tags/articles/661/studenti",
]

# Output directory specific for Politika articles
POLITIKA_OUT_DIR = OUT_DIR / "politika"
POLITIKA_OUT_DIR.mkdir(parents=True, exist_ok=True)

POLITIKA_MONTHS = {
    **MONTHS,
    "јан": 1,
    "феб": 2,
    "мар": 3,
    "апр": 4,
    "мај": 5,
    "јун": 6,
    "јул": 7,
    "авг": 8,
    "сеп": 9,
    "окт": 10,
    "нов": 11,
    "дец": 12,
}


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


def parse_datetime_value(value: str | None):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_politika_date(text: str):
    """
    Examples:
    Среда, 22.04.2026. у 09:54
    29.05.2026
    10. јан. 2025.
    данас 12:33
    јуче 18:10
    """
    text = clean_text(text).lower()

    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\.?", text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        return date(year, month, day)

    match = re.search(r"(\d{1,2})\.\s*([a-zčćšđžа-шђжљњћ]+)\.?\s*(\d{4})", text)
    if match:
        day = int(match.group(1))
        month_key = match.group(2)[:3]
        year = int(match.group(3))
        month = POLITIKA_MONTHS.get(month_key)
        if month:
            return date(year, month, day)

    today = date.today()
    if re.search(r"\b(?:данас|danas)\b", text):
        return today
    if re.search(r"\b(?:јуче|juče|juce)\b", text):
        return today - timedelta(days=1)

    return None


def is_article_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc != urlparse(BASE_URL).netloc:
        return False

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    return len(parts) >= 4 and parts[0] == "scc" and parts[1] == "clanak" and parts[2].isdigit()


def extract_article_links(soup: BeautifulSoup) -> list[str]:
    links = []
    seen = set()
    root = soup.select_one("article .article-content") or soup.find("article") or soup

    for a in root.find_all("a", href=True):
        url = normalize_url(a["href"])

        if not is_article_url(url) or url in seen:
            continue

        seen.add(url)
        links.append(url)

    return links


def is_tag_page_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc != urlparse(BASE_URL).netloc:
        return False

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    return len(parts) >= 5 and parts[0:3] == ["scc", "tags", "articles"] and parts[3].isdigit()


def get_page_number(url: str) -> int:
    match = re.search(r"/page:(\d+)/?", urlparse(url).path)
    return int(match.group(1)) if match else 1


def find_next_page(soup: BeautifulSoup, current_url: str):
    root = soup.select_one(".pagination") or soup

    for a in root.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True)).casefold()
        rel = {value.casefold() for value in a.get("rel", [])}
        url = normalize_url(a["href"])

        if not is_tag_page_url(url):
            continue
        if "next" in rel or text in {"следећа", "sledeća", "sledece", "next", ">"}:
            return url

    page_numbers = []
    for a in root.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        url = normalize_url(a["href"])

        if text.isdigit() and is_tag_page_url(url):
            page_numbers.append((int(text), url))

    current_num = get_page_number(current_url)
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

            main_entity = item.get("mainEntity")
            if isinstance(main_entity, list):
                items.extend(main_entity)
            elif isinstance(main_entity, dict):
                items.append(main_entity)

            yield item


def extract_json_ld_metadata(soup: BeautifulSoup) -> tuple[str | None, date | None]:
    author = None
    published_date = None

    for item in iter_json_ld_items(soup):
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

    article = soup.find("article") or soup

    if not published_date:
        title = soup.find("h1")
        search_root = title.find_all_next(string=True, limit=80) if title else article.find_all(string=True)
        for text_node in search_root:
            parsed_date = parse_politika_date(str(text_node))
            if parsed_date:
                published_date = parsed_date
                break

    if not author and published_date:
        date_pattern = re.compile(r"\d{1,2}\.\d{1,2}\.\d{4}")
        for text_node in article.find_all(string=True):
            text = clean_text(str(text_node))
            if date_pattern.search(text):
                parent_text = clean_text(text_node.parent.get_text(" ", strip=True))
                parts = date_pattern.split(parent_text, maxsplit=1)
                if len(parts) == 2:
                    author_candidate = clean_text(
                        re.sub(r"^[\s.]*у\s+\d{1,2}:\d{2}", "", parts[1], flags=re.I)
                    )
                    author = author_candidate or author
                break

    return author, published_date


def extract_article(url: str, tag_page: str) -> dict | None:
    soup = get_soup(url)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None

    author, published_date = extract_author_and_date(soup)

    article = soup.select_one("article .article-content") or soup.find("article") or soup
    paragraphs = []

    for p in article.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))

        if len(txt) < 30:
            continue

        skip_phrases = [
            "Developed by",
            "Коментар успешно додат",
            "Комeнтар успeшно додат",
            "Ваш коментар ће бити видљив",
            "Ваш комeнтар ћe бити видљив",
            "Повезане Теме",
            "Повезане теме",
            "Прочитајте још",
            "Pročitajte još",
            "Пратите нас",
            "Pratite nas",
            "Најновије",
            "Najnovije",
            "Најчитаније",
            "Najčitanije",
            "Коментари",
            "Komentari",
            "Политика онлајн",
            "Politika Online",
        ]

        if any(phrase.lower() in txt.lower() for phrase in skip_phrases):
            continue

        paragraphs.append(txt)

    text = "\n\n".join(paragraphs)

    if not title or not published_date or not text:
        return None

    return {
        "source": "Politika",
        "portal": "politika.rs",
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

    for path in POLITIKA_OUT_DIR.glob("*.json"):
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
    path = POLITIKA_OUT_DIR / filename

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

    print(f"Loaded {len(seen_urls)} already scraped Politika URLs")

    for start_url in START_URLS:
        total_saved += scrape_tag(start_url, seen_urls)

    print(f"\nDone. Saved {total_saved} new articles to {POLITIKA_OUT_DIR}")


if __name__ == "__main__":
    main()
