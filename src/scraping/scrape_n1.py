from datetime import date, datetime
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraping import MONTHS, OUT_DIR
from scraping.base_scraper import BaseScraper


class N1Scraper(BaseScraper):
    BASE_URL = "https://n1info.rs"
    START_URLS = ["https://n1info.rs/tag/blokade"]
    OUT_DIR = OUT_DIR / "n1"
    NAME = "N1"
    NORMALIZE_TRAILING_SLASH = True

    def parse_serbian_date(self, text: str):
        text = self.clean_text(text).lower()

        pattern = r"(\d{1,2})\.\s*([a-zčćšđž]+)\.?\s*(\d{4})"
        match = re.search(pattern, text)

        if not match:
            return None

        day = int(match.group(1))
        month_key = match.group(2)[:3]
        year = int(match.group(3))

        month = MONTHS.get(month_key)
        if not month:
            return None

        return date(year, month, day)

    def is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        if parsed.netloc != urlparse(self.BASE_URL).netloc:
            return False
        return bool(re.fullmatch(r"/(?:vesti|ekonomija|srbija)/[^/]+", path))

    def extract_article_links(self, soup: BeautifulSoup) -> list[str]:
        links = set()

        for a in soup.find_all("a", href=True):
            url = urljoin(self.BASE_URL, a["href"])
            parsed = urlparse(url)
            path = parsed.path.rstrip("/")
            normalized = f"{parsed.scheme}://{parsed.netloc}{path}/"

            if not self.is_article_url(normalized):
                continue

            links.add(normalized)

        return sorted(links)

    def find_next_page(self, soup: BeautifulSoup, current_url: str):
        for a in soup.find_all("a", href=True):
            text = self.clean_text(a.get_text(" ", strip=True)).casefold()
            rel = {value.casefold() for value in a.get("rel", [])}

            if "next" in rel or "sledeća" in text:
                return urljoin(self.BASE_URL, a["href"])

        return None

    def extract_article(self, url: str, tag_page: str) -> dict | None:
        soup = self.get_soup(url)

        title_tag = soup.find("h1")
        title = self.clean_text(title_tag.get_text()) if title_tag else None

        author = None
        author_label = soup.find(string=re.compile(r"autor", re.I))
        if author_label:
            parent_text = self.clean_text(author_label.parent.get_text(" ", strip=True))
            author = parent_text.replace("autor:", "").strip()

        page_text = soup.get_text(" ", strip=True)
        published_date = self.parse_serbian_date(page_text)

        article = soup.find("article") or soup

        paragraphs = []
        for p in article.find_all("p"):
            txt = self.clean_text(p.get_text(" ", strip=True))

            if len(txt) < 30:
                continue

            skip_phrases = [
                "Podeli",
                "Pročitajte još",
                "Pratite nas",
                "Oglas",
                "Koje je vaše mišljenje",
                "Pridružite se diskusiji",
            ]

            if any(phrase.lower() in txt.lower() for phrase in skip_phrases):
                continue

            paragraphs.append(txt)

        text = "\n\n".join(paragraphs)

        if not title or not published_date or not text:
            return None

        return {
            "source": "N1",
            "portal": "n1info.rs",
            "tag_page": tag_page,
            "url": url,
            "title": title,
            "author": author,
            "published_date": published_date.isoformat(),
            "text": text,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }


def main():
    return N1Scraper().run()


if __name__ == "__main__":
    main()
