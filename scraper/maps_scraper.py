"""Playwright-based Google Maps scraper for Moroccan barbershops.

This method scrapes Google Maps search results directly using a headless browser.
No API key required, but may be slower and less reliable than the Places API.

Uses stealth techniques to avoid detection.
"""

import asyncio
import logging
import re
import time
from typing import Optional

from .cities import MOROCCAN_CITIES, SEARCH_QUERIES
from .utils import deduplicate

logger = logging.getLogger(__name__)


def _extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text."""
    if not text:
        return None
    patterns = [
        r"\+212\s?\d[\d\s\-]{8,12}",
        r"0[5-7]\d[\d\s\-]{7,11}",
        r"\+\d{1,3}[\d\s\-]{8,15}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text.replace("\u202a", "").replace("\u202c", ""))
        if match:
            return match.group(0).strip()
    return None


def _extract_city_from_url(url: str) -> str:
    """Extract city from Google Maps URL."""
    for city_name, _, _, _ in MOROCCAN_CITIES:
        if city_name.lower().replace(" ", "+") in url.lower():
            return city_name
    return ""


async def _scroll_results(page, max_scrolls: int = 10) -> int:
    """Scroll through search results to load more listings."""
    scroll_count = 0
    last_count = 0

    for _ in range(max_scrolls):
        try:
            results_panel = page.locator("div[role='feed']").first
            if await results_panel.count() == 0:
                break

            await results_panel.evaluate(
                "el => el.scrollTop = el.scrollHeight"
            )
            await page.wait_for_timeout(1500)

            current_count = await page.locator("div[role='feed'] > div > div").count()
            if current_count == last_count:
                await page.mouse.wheel(0, 800)
                await page.wait_for_timeout(1500)
                current_count = await page.locator("div[role='feed'] > div > div").count()
                if current_count == last_count:
                    break
            last_count = current_count
            scroll_count += 1

        except Exception as e:
            logger.debug(f"Scroll error: {e}")
            break

    return scroll_count


async def _extract_from_listing(page, element) -> dict:
    """Extract shop data from a listing container element."""
    shop = {
        "name": "",
        "address": "",
        "city": "",
        "phone": "",
        "website": "",
        "rating": None,
        "reviews": None,
        "latitude": None,
        "longitude": None,
        "category": "",
        "status": "OPERATIONAL",
        "source": "google_maps",
        "maps_url": "",
    }

    try:
        # Name from the overlay link's aria-label
        overlay = element.locator("a.hfpxzc").first
        if await overlay.count() > 0:
            label = await overlay.get_attribute("aria-label") or ""
            shop["name"] = label.strip()
            href = await overlay.get_attribute("href") or ""
            if href:
                shop["maps_url"] = href

        # Content div
        content = element.locator("div.bfdHYd").first
        if await content.count() == 0:
            content = element

        # Rating from the stars span
        rating_el = content.locator("span[role='img']").first
        if await rating_el.count() > 0:
            rating_text = await rating_el.get_attribute("aria-label") or ""
            rating_match = re.search(r"([\d,]+)\s*étoiles", rating_text)
            if rating_match:
                shop["rating"] = float(rating_match.group(1).replace(",", "."))
            review_match = re.search(r"([\d\u202f]+)\s*avis", rating_text)
            if review_match:
                reviews_clean = review_match.group(1).replace("\u202f", "").replace(" ", "")
                shop["reviews"] = int(reviews_clean)

        # Address and phone from the W4Efsd info sections
        info_text = ""
        try:
            info_els = content.locator("div.W4Efsd")
            info_count = await info_els.count()
            for i in range(min(info_count, 6)):
                text = (await info_els.nth(i).inner_text()).strip()
                if text:
                    info_text += text + " | "
        except Exception:
            pass

        if info_text:
            phone = _extract_phone(info_text)
            if phone:
                shop["phone"] = phone

            parts = [p.strip() for p in info_text.split("|") if p.strip()]
            for part in parts:
                if not shop["address"] and len(part) > 10 and not part[0].isdigit():
                    shop["address"] = part

        shop["category"] = "Barbershop"

    except Exception as e:
        logger.debug(f"Error extracting listing: {e}")

    return shop


async def _get_place_details(page, shop: dict) -> dict:
    """Navigate to place page and extract phone/website from structured data."""
    maps_url = shop.get("maps_url", "")
    if not maps_url:
        return shop

    try:
        await page.goto(maps_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        full_html = await page.content()

        patterns = [
            r'\+212\s?\d[\d\s\-\(\)]{8,12}',
            r'0[5-7]\d[\d\s\-\(\)]{7,11}',
            r'212\s?\d[\d\s\-\(\)]{8,12}',
        ]
        for p in patterns:
            match = re.search(p, full_html.replace("\u202a", "").replace("\u202c", ""))
            if match:
                phone = match.group(0).strip()
                if phone:
                    shop['phone'] = phone
                    break

        if not shop.get('website'):
            links = page.locator("a[href*='http']")
            count = await links.count()
            for i in range(min(count, 20)):
                href = await links.nth(i).get_attribute("href") or ""
                if href.startswith("http") and "google" not in href and "maps" not in href:
                    shop['website'] = href
                    break

    except Exception as e:
        logger.debug(f"Error getting details for {shop.get('name')}: {e}")

    return shop


async def scrape_city_playwright(
    city_name: str,
    lat: float,
    lng: float,
    radius: int,
    context,
    headless: bool = True,
    max_listings: int = 20,
    get_details: bool = False,
) -> list[dict]:
    """Scrape barbershops for a single city using Playwright."""
    shops = []

    queries = SEARCH_QUERIES

    for query in queries:
        search_url = f"https://www.google.com/maps/search/{query}+{city_name}+morocco/@{lat},{lng},{14 - radius//5}z"

        page = await context.new_page()
        try:
            logger.info(f"  Navigating: {query} in {city_name}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            try:
                consent_btn = page.locator(
                    "button[aria-label*='Accept'], button[aria-label*='Tout accepter'], "
                    "button[aria-label*='Accepter'], span[class*='consent'] button"
                ).first
                if await consent_btn.count() > 0:
                    await consent_btn.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            try:
                await page.wait_for_selector(
                    "div[role='feed']",
                    timeout=10000,
                )
            except Exception:
                logger.warning(f"  No results loaded for '{query}' in {city_name}")
                continue

            scrolls = await _scroll_results(page, max_scrolls=5)

            containers = page.locator("div[role='feed'] > div > div")
            total = await containers.count()
            logger.info(f"  Found {total} containers ({scrolls} scrolls)")

            seen_names = set()
            collected = 0
            for i in range(total):
                if collected >= max_listings:
                    break
                try:
                    has_overlay = await containers.nth(i).locator("a.hfpxzc").count()
                    if not has_overlay:
                        continue

                    shop = await _extract_from_listing(page, containers.nth(i))
                    if shop["name"] and shop["name"] not in seen_names:
                        shop["city"] = city_name
                        seen_names.add(shop["name"])
                        shops.append(shop)
                        collected += 1
                except Exception as e:
                    logger.debug(f"  Error extracting listing {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"  Error scraping {city_name} with '{query}': {e}")
        finally:
            await page.close()

        await asyncio.sleep(2)

    if get_details and shops:
        logger.info(f"  Getting details for {len(shops)} shops...")
        detail_page = await context.new_page()
        try:
            for shop in shops:
                if not shop.get("phone"):
                    shop = await _get_place_details(detail_page, shop)
                await asyncio.sleep(1)
        finally:
            await detail_page.close()

    return shops


async def scrape_all_playwright(
    headless: bool = True,
    max_cities: int = 10,
    max_listings: int = 20,
    get_details: bool = False,
) -> list[dict]:
    """Scrape all Moroccan cities using Playwright."""
    from playwright.async_api import async_playwright

    all_shops = []
    cities = MOROCCAN_CITIES[:max_cities]

    logger.info(
        f"Starting Playwright scrape: {len(cities)} cities, "
        f"headless={headless}, details={get_details}"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="fr-MA",
            geolocation={"latitude": 33.5731, "longitude": -7.5898},
            permissions=["geolocation"],
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        for i, (city_name, lat, lng, radius) in enumerate(cities):
            logger.info(f"\n[{i+1}/{len(cities)}] {city_name}")
            shops = await scrape_city_playwright(
                city_name, lat, lng, radius, context,
                headless, max_listings, get_details,
            )
            all_shops.extend(shops)
            logger.info(f"  Found {len(shops)} shops")

        await browser.close()

    all_shops = deduplicate(all_shops)

    return all_shops


def scrape_all_sync(
    headless: bool = True,
    max_cities: int = 10,
    max_listings: int = 20,
    get_details: bool = False,
) -> list[dict]:
    """Synchronous wrapper for the async scraper."""
    return asyncio.run(
        scrape_all_playwright(headless, max_cities, max_listings, get_details)
    )
