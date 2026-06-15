from datetime import date, datetime, timedelta
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraping import MONTHS, OUT_DIR
from scraping.base_scraper import BaseScraper


class KurirScraper(BaseScraper):
    BASE_URL = "https://www.kurir.rs"
    START_URLS = [
        "https://www.kurir.rs/tag/1172233/studenti-blokaderi",
        "https://www.kurir.rs/tag/1168427/studentske-blokade",
        "https://www.kurir.rs/tag/453819/studentski-protesti",
        "https://www.kurir.rs/tag/28550/studentski-protest",
        "https://www.kurir.rs/tag/32483/protest-studenata",
    ]
    OUT_DIR = OUT_DIR / "kurir"
    NAME = "Kurir"
    INCLUDE_JSON_LD_MAIN_ENTITY = True

    def parse_kurir_date(self, text: str):
        text = self.clean_text(text).lower()

        match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\.", text)
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
            "tag",
            "author",
            "najnovije",
            "arhiva",
            "marketing",
            "kontakt",
            "impressum",
            "politika-o-kolacicima",
            "politika-privatnosti",
            "uslovi-koriscenja",
        }
        if parts[0] in ignored_first_parts:
            return False

        return parts[-2].isdigit()

    def extract_article_links(self, soup: BeautifulSoup) -> list[str]:
        links = []
        seen = set()
        root = soup.select_one(".archive-acl.is-tag-archive") or soup.find("main") or soup

        for a in root.find_all("a", href=True):
            url = self.normalize_url(a["href"])
            text = self.clean_text(a.get_text(" ", strip=True)).casefold()

            if text in {"sledeća", "sledece", "next", "najnovije", "arhiva"}:
                continue
            if not self.is_article_url(url) or url in seen:
                continue

            seen.add(url)
            links.append(url)

        return links

    def is_tag_page_url(self, url: str) -> bool:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        return parsed.netloc == urlparse(self.BASE_URL).netloc and len(parts) >= 3 and parts[0] == "tag"

    def get_page_number(self, url: str) -> int:
        match = re.search(r"/page/(\d+)/?", urlparse(url).path)
        return int(match.group(1)) if match else 1

    def find_next_page(self, soup: BeautifulSoup, current_url: str):
        root = soup.select_one(".archive-acl.is-tag-archive") or soup

        for a in root.find_all("a", href=True):
            text = self.clean_text(a.get_text(" ", strip=True)).casefold()
            rel = {value.casefold() for value in a.get("rel", [])}
            url = self.normalize_url(a["href"])

            if not self.is_tag_page_url(url):
                continue
            if "next" in rel or text in {"sledeća", "sledece", "next", ">"}:
                return url

        page_numbers = []
        for a in root.find_all("a", href=True):
            text = self.clean_text(a.get_text(" ", strip=True))
            url = self.normalize_url(a["href"])

            if text.isdigit() and self.is_tag_page_url(url):
                page_numbers.append((int(text), url))

        current_num = self.get_page_number(current_url)
        for page_num, url in sorted(page_numbers):
            if page_num == current_num + 1:
                return url

        return None

    def extract_json_ld_metadata(self, soup: BeautifulSoup) -> tuple[str | None, date | None]:
        author = None
        published_date = None

        for item in self.iter_json_ld_items(soup):
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
            for attr in (
                {"property": "article:published_time"},
                {"name": "date"},
                {"name": "pubdate"},
            ):
                meta_date = soup.find("meta", attrs=attr)
                if meta_date and meta_date.get("content"):
                    published_date = self.parse_datetime_value(meta_date["content"])
                    if published_date:
                        break

        time_tag = soup.find("time")
        if time_tag and not published_date:
            published_date = self.parse_datetime_value(time_tag.get("datetime"))
            if not published_date:
                published_date = self.parse_kurir_date(time_tag.get_text(" ", strip=True))

        if not author:
            author_label = soup.find(
                string=lambda text: (
                    text
                    and re.search(r"\b(?:autor|prenosi)\b", text, re.I)
                    and text.parent
                    and text.parent.name not in {"script", "style"}
                )
            )
            if author_label and author_label.parent:
                parent_text = self.clean_text(author_label.parent.get_text(" ", strip=True))
                author = self.clean_text(re.sub(r"(autor|prenosi):?", "", parent_text, flags=re.I))

        if not published_date:
            title = soup.find("h1")
            search_root = title.find_all_next(string=True, limit=80) if title else soup.find_all(string=True)
            for text_node in search_root:
                parsed_date = self.parse_kurir_date(str(text_node))
                if parsed_date:
                    published_date = parsed_date
                    break

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
                "Podeli",
                "Pročitajte još",
                "Procitajte još",
                "Ne propustite",
                "Pratite nas",
                "Oglas",
                "Slušaj vest",
                "Bonus video",
                "Najnovije",
                "Najčitanije",
                "Najcitanije",
                "Komentari",
                "Tagovi",
                "Kurir.rs",
                "Kurir Politika",
                "Dodajte Kurir",
                "Budi deo Kurir zajednice",
                "Preuzmite našu aplikaciju",
            ]

            if any(phrase.lower() in txt.lower() for phrase in skip_phrases):
                continue

            paragraphs.append(txt)

        text = "\n\n".join(paragraphs)

        if not title or not published_date or not text:
            return None

        return {
            "source": "Kurir",
            "portal": "kurir.rs",
            "tag_page": tag_page,
            "url": url,
            "title": title,
            "author": author,
            "published_date": published_date.isoformat(),
            "text": text,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }


def main():
    return KurirScraper().run()


if __name__ == "__main__":
    main()
