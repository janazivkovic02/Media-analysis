from datetime import date, datetime, timedelta
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from scraping import MONTHS, OUT_DIR
from scraping.base_scraper import BaseScraper


class BlicScraper(BaseScraper):
    BASE_URL = "https://www.blic.rs"
    START_URLS = [
        "https://www.blic.rs/studentske-blokade",
        "https://www.blic.rs/blokade-studenata",
        "https://www.blic.rs/studenti-u-blokadi",
        "https://www.blic.rs/studentski-protesti",
    ]
    OUT_DIR = OUT_DIR / "blic"
    NAME = "Blic"
    FILENAME_SLUG_INDEX = -2

    def normalize_page_url(self, url: str) -> str:
        parsed = urlparse(urljoin(self.BASE_URL, url))
        query = urlencode(parse_qs(parsed.query), doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", query, ""))

    def parse_blic_date(self, text: str):
        text = self.clean_text(text).lower()

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

    def is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)

        if parsed.netloc != urlparse(self.BASE_URL).netloc:
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

    def extract_article_links(self, soup: BeautifulSoup) -> list[str]:
        links = []
        seen = set()
        roots = soup.select(".section__left--inner-left") or [soup.find("main") or soup]

        for root in roots:
            for article in root.select("article.news-box__item"):
                a = article.find("a", href=True)
                if not a:
                    continue

                url = self.normalize_url(a["href"])
                if not self.is_article_url(url) or url in seen:
                    continue

                seen.add(url)
                links.append(url)

        return links

    def get_page_number(self, url: str) -> int:
        parsed = urlparse(url)
        value = parse_qs(parsed.query).get("strana", ["1"])[0]
        return int(value) if value.isdigit() else 1

    def find_next_page(self, soup: BeautifulSoup, current_url: str):
        form = soup.find("form", id="pagination-next-form")
        next_input = form.find("input", attrs={"name": "strana"}) if form else None

        if next_input and next_input.get("value", "").isdigit():
            parsed = urlparse(current_url)
            query = parse_qs(parsed.query)
            query["strana"] = [next_input["value"]]
            return self.normalize_page_url(
                urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(query, doseq=True), ""))
            )

        current_num = self.get_page_number(current_url)
        for a in soup.find_all("a", href=True):
            text = self.clean_text(a.get_text(" ", strip=True)).casefold()
            if text in {"sledeća", "sledece", "next", ">"}:
                href = a["href"]
                if href == "#":
                    continue
                return self.normalize_page_url(href)

        page_numbers = []
        for a in soup.find_all("a", href=True):
            text = self.clean_text(a.get_text(" ", strip=True))
            if text.isdigit():
                url = self.normalize_page_url(a["href"])
                if urlparse(url).netloc == urlparse(self.BASE_URL).netloc:
                    page_numbers.append((int(text), url))

        for page_num, url in sorted(page_numbers):
            if page_num == current_num + 1:
                return url

        return None

    def extract_json_ld_metadata(self, soup: BeautifulSoup) -> tuple[str | None, date | None]:
        author = None
        published_date = None

        for item in self.iter_json_ld_items(soup):
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]

            if "NewsArticle" not in types and "Article" not in types:
                continue

            if not published_date:
                published_date = self.parse_datetime_value(item.get("datePublished"))

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

        return self.clean_text(author) if author else None, published_date

    def extract_author_and_date(self, soup: BeautifulSoup):
        author, published_date = self.extract_json_ld_metadata(soup)

        if not author:
            meta_author = soup.find("meta", attrs={"name": "author"})
            if meta_author and meta_author.get("content"):
                author = self.clean_text(meta_author["content"])

        if not published_date:
            meta_date = soup.find("meta", attrs={"property": "article:published_time"})
            if meta_date and meta_date.get("content"):
                published_date = self.parse_datetime_value(meta_date["content"])

        time_tag = soup.find("time")
        if time_tag and not published_date:
            published_date = self.parse_datetime_value(time_tag.get("datetime"))
            if not published_date:
                published_date = self.parse_blic_date(time_tag.get_text(" ", strip=True))

        if not author:
            author_tag = soup.select_one(".article__author-name")
            if author_tag:
                author = self.clean_text(author_tag.get_text(" ", strip=True))

        if not published_date:
            published_date = self.parse_blic_date(soup.get_text(" ", strip=True))

        return author, published_date

    def extract_article(self, url: str, tag_page: str) -> dict | None:
        soup = self.get_soup(url)

        title_tag = soup.find("h1")
        title = self.clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None

        author, published_date = self.extract_author_and_date(soup)

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
            txt = self.clean_text(p.get_text(" ", strip=True))

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


def main():
    return BlicScraper().run()


if __name__ == "__main__":
    main()
