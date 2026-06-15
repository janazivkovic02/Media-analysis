from datetime import date, datetime, timedelta
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraping import OUT_DIR
from scraping.base_scraper import BaseScraper


class DanasScraper(BaseScraper):
    BASE_URL = "https://www.danas.rs"
    TAGS = [
        "studenti-u-blokadi",
        "studentske-blokade",
        "studentski-protest",
    ]
    START_URLS = [f"https://www.danas.rs/tag/{tag}/" for tag in TAGS]
    OUT_DIR = OUT_DIR / "danas"
    NAME = "Danas"
    NORMALIZE_TRAILING_SLASH = True

    def parse_danas_date(self, text: str):
        text = self.clean_text(text).lower()

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

    def is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)

        if parsed.netloc != urlparse(self.BASE_URL).netloc:
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

    def extract_article_links(self, soup: BeautifulSoup) -> list[str]:
        links = []
        seen = set()
        root = soup.find("main") or soup

        for heading in root.find_all(["h2", "h3"]):
            heading_text = self.clean_text(heading.get_text(" ", strip=True)).casefold()
            if heading_text in {"kretanje članaka", "najnovije", "najčitanije"}:
                break

            a = heading.find("a", href=True)
            if not a:
                continue

            url = self.normalize_url(a["href"])
            if not self.is_article_url(url) or url in seen:
                continue

            seen.add(url)
            links.append(url)

        return links

    def get_page_number(self, url: str) -> int:
        match = re.search(r"/page/(\d+)/?", urlparse(url).path)
        return int(match.group(1)) if match else 1

    def find_next_page(self, soup: BeautifulSoup, current_url: str):
        for a in soup.find_all("a", href=True):
            text = self.clean_text(a.get_text(" ", strip=True)).casefold()
            rel = {value.casefold() for value in a.get("rel", [])}

            if "next" in rel or text in {"sledeća", "sledece", "next", ">"}:
                return self.normalize_url(a["href"])

        page_numbers = []
        for a in soup.find_all("a", href=True):
            text = self.clean_text(a.get_text(" ", strip=True))
            if text.isdigit():
                page_numbers.append((int(text), self.normalize_url(a["href"])))

        if page_numbers:
            current = soup.find("span", class_=re.compile(r"current", re.I))
            current_text = self.clean_text(current.get_text()) if current else ""
            current_num = int(current_text) if current_text.isdigit() else self.get_page_number(current_url)

            for page_num, url in sorted(page_numbers):
                if page_num == current_num + 1:
                    return url

        return None

    def extract_author_and_date(self, soup: BeautifulSoup):
        author = None
        published_date = None

        time_tag = soup.find("time")
        if time_tag:
            datetime_value = time_tag.get("datetime")
            if datetime_value:
                published_date = self.parse_datetime_value(datetime_value)
            if not published_date:
                published_date = self.parse_danas_date(time_tag.get_text(" ", strip=True))

        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = self.clean_text(meta_author["content"])

        if not author:
            title = soup.find("h1")
            if title:
                for element in title.find_all_next(string=True, limit=20):
                    text = self.clean_text(str(element))
                    if self.parse_danas_date(text):
                        parts = re.split(
                            r"\d{1,2}\.\d{1,2}\.\d{4}\.|danas|juče|juce",
                            text,
                            maxsplit=1,
                            flags=re.I,
                        )
                        author = self.clean_text(parts[0]) if parts and self.clean_text(parts[0]) else None
                        published_date = published_date or self.parse_danas_date(text)
                        break

        if not published_date:
            published_date = self.parse_danas_date(soup.get_text(" ", strip=True))

        return author, published_date

    def extract_article(self, url: str, tag_page: str) -> dict | None:
        soup = self.get_soup(url)

        title_tag = soup.find("h1")
        title = self.clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None

        author, published_date = self.extract_author_and_date(soup)

        article = soup.find("article") or soup.find("main") or soup
        paragraphs = []

        for p in article.find_all("p"):
            txt = self.clean_text(p.get_text(" ", strip=True))

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


def main():
    return DanasScraper().run()


if __name__ == "__main__":
    main()
