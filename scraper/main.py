"""Main entry point for the Qutbi Leads Scraper.

Usage:
    python -m scraper.main                     # Playwright mode (default)
    python -m scraper.main --api-key KEY       # Google Places API mode
    python -m scraper.main --headless false    # Show browser
    python -m scraper.main --cities 5          # Scrape 5 cities only
    python -m scraper.main --max-listings 50   # Max 50 listings per city
    python -m scraper.main --details           # Get detailed info (slower)
    python -m scraper.main --format json       # Output as JSON instead of CSV
"""

import argparse
import logging
import sys
import os

from .utils import save_to_csv, save_to_json, print_summary, deduplicate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Qutbi Leads Scraper - Moroccan Barbershop Lead Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scraper.main                        # Scrape using Playwright (free)
  python -m scraper.main --api-key YOUR_KEY     # Scrape using Google Places API
  python -m scraper.main --cities 3 --headless false
  python -m scraper.main --format json --max-listings 50
        """,
    )

    parser.add_argument(
        "--method",
        choices=["playwright", "places_api", "yelo"],
        default="playwright",
        help="Scraping method (default: playwright)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("GOOGLE_PLACES_API_KEY", ""),
        help="Google Places API key (or set GOOGLE_PLACES_API_KEY env var)",
    )
    parser.add_argument(
        "--headless",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=True,
        help="Run browser in headless mode (default: true)",
    )
    parser.add_argument(
        "--cities",
        type=int,
        default=10,
        help="Number of cities to scrape (default: 10, max: 20)",
    )
    parser.add_argument(
        "--max-listings",
        type=int,
        default=20,
        help="Max listings per city per query (default: 20)",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Get detailed info for each shop (slower but more data)",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "both"],
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output filename",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("""
╔══════════════════════════════════════════════════════╗
║         QUTBI LEADS SCRAPER                          ║
║         Moroccan Barbershop Lead Generation          ║
╚══════════════════════════════════════════════════════╝
    """)

    if args.method == "places_api":
        if not args.api_key:
            print("[!] Google Places API key required for this method.")
            print("    Use --api-key YOUR_KEY or set GOOGLE_PLACES_API_KEY env var.")
            print("    Get one at: https://console.cloud.google.com/apis/credentials")
            sys.exit(1)

        logger.info(f"Using Google Places API method")
        logger.info(f"Scraping up to {args.cities} cities...")

        from .places_api import scrape_all

        shops = scrape_all(args.api_key, max_cities=args.cities)

    elif args.method == "yelo":
        logger.info("Using yelo.ma directory method")
        logger.info(f"Scraping {args.cities} cities...")

        from .directory_scraper import scrape_all_yelo_sync

        shops = scrape_all_yelo_sync(max_cities=args.cities, max_listings=args.max_listings)

    else:
        logger.info("Using Playwright (browser) method")
        logger.info(f"Scraping {args.cities} cities, headless={args.headless}")

        from .maps_scraper import scrape_all_sync

        shops = scrape_all_sync(
            headless=args.headless,
            max_cities=args.cities,
            max_listings=args.max_listings,
            get_details=args.details,
        )

    if not shops:
        logger.warning("No shops found. Try different parameters.")
        sys.exit(0)

    # Save results
    print(f"\n[+] Saving {len(shops)} shops...")

    if args.format in ("csv", "both"):
        csv_path = save_to_csv(shops, args.output)
        print(f"  CSV  -> {csv_path}")

    if args.format in ("json", "both"):
        json_name = args.output.replace(".csv", ".json") if args.output and args.output.endswith(".csv") else None
        json_path = save_to_json(shops, json_name)
        print(f"  JSON -> {json_path}")

    # Print summary
    print_summary(shops)

    print("\n[+] Done! Use these leads for your Qutbi SaaS outreach. 🚀")


if __name__ == "__main__":
    main()