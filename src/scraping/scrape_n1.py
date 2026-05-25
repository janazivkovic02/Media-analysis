from datetime import date, datetime
import json # For saving articles in JSON format
import re # For regular expressions in date parsing and text cleaning
import time
import hashlib # For generating unique filenames based on article URLs
from urllib.parse import urljoin, urlparse # For handling URLs

import requests # For making HTTP requests and handling responses
from bs4 import BeautifulSoup # For parsing HTML content

from scraping import DATE_FROM, DATE_TO, OUT_DIR, HEADERS, MONTHS

# This description can be added to README.md later
# This scraper systematically collects protest-related news articles from N1 Info
# by traversing the "blokade" tag archive.
# It identifies candidate article URLs, retrieves each article page,
# parses relevant metadata and textual content using BeautifulSoup,
# and continues through paginated archive pages until the specified date boundary is reached.
# Each extracted article is stored as a structured JSON document
# to support downstream analysis.

# Add: author field extraction, which is often present in the article metadata 
# Think about optimizing data storage, maybe one JSON file per article is not the best solution

# Scraper for N1 Info - https://n1info.rs
BASE_URL = "https://n1info.rs"
START_URL = "https://n1info.rs/tag/blokade"

# Output directory specific for N1 articles
N1_OUT_DIR = OUT_DIR / "n1"
N1_OUT_DIR.mkdir(parents=True, exist_ok=True) 

# Takes in url and returns BeautifulSoup object of the page content
def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20) # Set a timeout to avoid hanging on slow responses
    response.raise_for_status() # Raise an exception for HTTP errors
    response.encoding = "utf-8" # Ensure correct encoding for Serbian characters
    return BeautifulSoup(response.text, "html.parser")

# Cleans up text by collapsing multiple whitespace characters into a single space and stripping leading/trailing whitespace
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

# Parses Serbian date formats found in the article text and returns a date object
# It is used for extracting the published date of the article, which is crucial for filtering articles within the desired date range (DATE_FROM to DATE_TO)
def parse_serbian_date(text: str):
    """
    Primeri:
    01. mar. 2025. 11:43
    5. apr. 2025.
    """
    text = clean_text(text).lower()

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

# Extracts article links from the page soup by looking for anchor tags that match the expected URL pattern for articles on N1 Info. It filters out irrelevant links and returns a sorted list of unique article URLs.
def extract_article_links(soup: BeautifulSoup) -> list[str]:
    links = set()

    for a in soup.find_all("a", href=True):
        url = urljoin(BASE_URL, a["href"])
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        if parsed.netloc != urlparse(BASE_URL).netloc:
            continue
        if not re.fullmatch(r"/(?:vesti|ekonomija|srbija)/[^/]+", path):
            continue

        links.add(f"{parsed.scheme}://{parsed.netloc}{path}/")

    return sorted(links)

# Finds the URL of the next page in the pagination by looking for anchor tags with "next" in their rel attribute or "sledeća" in their text. 
# This allows the scraper to navigate through multiple pages of articles tagged with "blokade" on N1 Info.
def find_next_page(soup: BeautifulSoup):
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True)).casefold()
        rel = {value.casefold() for value in a.get("rel", [])}

        if "next" in rel or "sledeća" in text:
            return urljoin(BASE_URL, a["href"])

    return None

# Extracts relevant information from an article page, including title, author, published date, and main text content.
# It performs various cleaning and filtering steps to ensure the extracted data is of high quality and relevant to the topic of interest.
# The function returns a dictionary containing the extracted information or None if the article does not meet the criteria 
# (e.g., missing title, published date, or text).
def extract_article(url: str) -> dict | None:
    soup = get_soup(url)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text()) if title_tag else None

    author = None
    author_label = soup.find(string=re.compile(r"autor", re.I))
    if author_label:
        parent_text = clean_text(author_label.parent.get_text(" ", strip=True))
        author = parent_text.replace("autor:", "").strip()

    page_text = soup.get_text(" ", strip=True)
    published_date = parse_serbian_date(page_text)

    article = soup.find("article") or soup

    paragraphs = []
    for p in article.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))

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
        "tag_page": START_URL,
        "url": url,
        "title": title,
        "author": author,
        "published_date": published_date.isoformat(),
        "text": text,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
    }

# Generates a unique filename for each article based on its URL by creating an MD5 hash of the URL and combining it with a cleaned version of the article's slug 
# This ensures that each article is saved with a consistent and unique filename in the output directory.
def make_filename(url: str) -> str:
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)
    return f"{slug}_{h}.json"

# Saves the extracted article information as a JSON file in the output directory.
def save_article(article: dict):
    filename = make_filename(article["url"])
    path = N1_OUT_DIR / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)

# Main function that orchestrates the scraping process by navigating through the tag pages, extracting article links, 
# and saving relevant articles within the specified date range. 
# It also handles pagination and ensures that the scraper does not revisit already seen URLs.
def main():
    current_url = START_URL
    seen_urls = set()
    saved = 0
    page_num = 1

    while current_url:
        print(f"\n[PAGE {page_num}] {current_url}")
        soup = get_soup(current_url)

        article_links = extract_article_links(soup)
        print(f"Found {len(article_links)} candidate article links")

        page_dates = []

        for url in article_links:
            if url in seen_urls:
                continue

            seen_urls.add(url)

            try:
                article = extract_article(url)
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
            print("Reached articles older than DATE_FROM. Stopping.")
            break

        current_url = find_next_page(soup)
        page_num += 1

        time.sleep(2)

    print(f"\nDone. Saved {saved} articles to {N1_OUT_DIR}")


if __name__ == "__main__":
    main()
