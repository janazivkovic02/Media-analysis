import argparse
from concurrent.futures import ThreadPoolExecutor

from scraping.scrape_blic import BlicScraper
from scraping.scrape_danas import DanasScraper
from scraping.scrape_kurir import KurirScraper
from scraping.scrape_n1 import N1Scraper
from scraping.scrape_nova import NovaScraper
from scraping.scrape_politika import PolitikaScraper


SCRAPERS = {
    "blic": BlicScraper,
    "danas": DanasScraper,
    "kurir": KurirScraper,
    "n1": N1Scraper,
    "nova": NovaScraper,
    "politika": PolitikaScraper,
}


def run_scraper(portal: str) -> int:
    print(f"\n=== Running {portal} ===")
    return SCRAPERS[portal]().run()


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape articles from configured Serbian news portals.")
    parser.add_argument(
        "--portals",
        nargs="+",
        choices=sorted(SCRAPERS),
        default=list(SCRAPERS),
        help="Portal scraper(s) to run. Defaults to all portals.",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run selected scrapers in parallel with ThreadPoolExecutor.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    portals = args.portals

    if args.parallel:
        with ThreadPoolExecutor(max_workers=len(portals)) as executor:
            results = dict(zip(portals, executor.map(run_scraper, portals)))
    else:
        results = {portal: run_scraper(portal) for portal in portals}

    total = sum(results.values())
    print("\n=== Scraping complete ===")
    for portal, saved in results.items():
        print(f"{portal}: {saved} new articles")
    print(f"total: {total} new articles")
    return total


if __name__ == "__main__":
    main()
