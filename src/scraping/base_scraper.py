from abc import ABC, abstractmethod
from datetime import date, datetime
import hashlib
import json
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scraping import DATE_FROM, DATE_TO, HEADERS


class BaseScraper(ABC):
    BASE_URL: str
    START_URLS: list[str]
    OUT_DIR = None
    NAME: str
    FILENAME_SLUG_INDEX = -1
    NORMALIZE_TRAILING_SLASH = False
    INCLUDE_JSON_LD_MAIN_ENTITY = False

    def __init__(self):
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)

    def get_soup(self, url: str) -> BeautifulSoup:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"
        return BeautifulSoup(response.text, "html.parser")

    def clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(urljoin(self.BASE_URL, url))
        path = parsed.path.rstrip("/")
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if self.NORMALIZE_TRAILING_SLASH:
            normalized += "/"
        return normalized

    def make_filename(self, url: str) -> str:
        h = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
        slug = url.rstrip("/").split("/")[self.FILENAME_SLUG_INDEX]
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)
        return f"{slug}_{h}.json"

    def load_existing_urls(self) -> set[str]:
        urls = set()

        for path in self.OUT_DIR.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    article = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            url = article.get("url")
            if url:
                urls.add(self.normalize_url(url))

        return urls

    def save_article(self, article: dict):
        filename = self.make_filename(article["url"])
        path = self.OUT_DIR / filename

        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)

    def scrape_tag(self, start_url: str, seen_urls: set[str]) -> int:
        current_url = start_url
        saved = 0
        page_num = 1

        while current_url:
            print(f"\n[TAG {start_url}] [PAGE {page_num}] {current_url}")
            soup = self.get_soup(current_url)

            article_links = self.extract_article_links(soup)
            print(f"Found {len(article_links)} candidate article links")

            page_dates = []

            for url in article_links:
                if url in seen_urls:
                    print(f"SKIP DUPLICATE: {url}")
                    continue

                seen_urls.add(url)

                try:
                    article = self.extract_article(url, start_url)
                except Exception as e:
                    print(f"ERROR: {url} -> {e}")
                    continue

                time.sleep(1)

                if article is None:
                    continue

                article_date = date.fromisoformat(article["published_date"])
                page_dates.append(article_date)

                if DATE_FROM <= article_date <= DATE_TO:
                    self.save_article(article)
                    saved += 1
                    print(f"SAVED {article_date}: {article['title']}")
                else:
                    print(f"SKIP  {article_date}: {article['title']}")

            if page_dates and max(page_dates) < DATE_FROM:
                print("Reached articles older than DATE_FROM. Stopping this tag.")
                break

            current_url = self.find_next_page(soup, current_url)
            page_num += 1

            time.sleep(2)

        return saved

    def parse_datetime_value(self, value: str | None):
        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    def iter_json_ld_items(self, soup: BeautifulSoup):
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

                if self.INCLUDE_JSON_LD_MAIN_ENTITY:
                    main_entity = item.get("mainEntity")
                    if isinstance(main_entity, list):
                        items.extend(main_entity)
                    elif isinstance(main_entity, dict):
                        items.append(main_entity)

                yield item

    def run(self) -> int:
        seen_urls = self.load_existing_urls()
        total_saved = 0

        print(f"Loaded {len(seen_urls)} already scraped {self.NAME} URLs")

        for start_url in self.START_URLS:
            total_saved += self.scrape_tag(start_url, seen_urls)

        print(f"\nDone. Saved {total_saved} new articles to {self.OUT_DIR}")
        return total_saved

    @abstractmethod
    def is_article_url(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract_article_links(self, soup: BeautifulSoup) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def extract_article(self, url: str, tag_page: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def find_next_page(self, soup: BeautifulSoup, current_url: str):
        raise NotImplementedError
