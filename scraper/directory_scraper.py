"""Scraper for free Moroccan business directories (yelo.ma).

Phone numbers visible on listing pages — no clicking needed.
"""

import asyncio
import logging
import re
import time
from typing import Optional

from .cities import MOROCCAN_CITIES
from .utils import deduplicate

logger = logging.getLogger(__name__)


def _extract_phone(text: str) -> Optional[str]:
    if not text:
        return None
    patterns = [
        r"\+212\s?\d[\d\s\-]{8,12}",
        r"0[5-7]\d[\d\s\-]{7,11}",
        r"\+\d{1,3}[\d\s\-]{8,15}",
        r"05\d[\d\s\-]{7,9}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return None


async def scrape_yelo_city(city_name: str, context, max_listings: int = 50) -> list[dict]:
    """Scrape barbershops from yelo.ma for a single city."""
    shops = []
    page_num = 1

    while len(shops) < max_listings:
        url = f"https://www.yelo.ma/category/coiffeurs/{page_num}/city:{city_name}"
        if page_num == 1:
            url = f"https://www.yelo.ma/category/Coiffeurs/city:{city_name}"

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)

            companies = page.locator("div.company")
            count = await companies.count()
            if count == 0:
                break

            for i in range(count):
                if len(shops) >= max_listings:
                    break
                try:
                    company = companies.nth(i)

                    name_el = company.locator("h3 a").first
                    name = (await name_el.inner_text()).strip() if await name_el.count() > 0 else ""

                    address_el = company.locator("div.address").first
                    address = (await address_el.inner_text()).strip() if await address_el.count() > 0 else ""

                    phone_el = company.locator(".s span b").first
                    phone = ""
                    if await phone_el.count() > 0:
                        raw = (await phone_el.inner_text()).strip()
                        phone = _extract_phone(raw) or raw

                    if name:
                        lower = name.lower()
                        exclude = ["pharmacie", "pharmac", "école", "ecole", "equipement", "bureau d'études", "b.e.r.i.c", "s.a.r.l", "s.a.", "maroc", "industrie"]
                        if any(k in lower for k in exclude):
                            continue
                        shops.append({
                            "name": name,
                            "address": address,
                            "city": city_name,
                            "phone": phone,
                            "phone_formatted": "",
                            "website": "",
                            "rating": None,
                            "reviews": None,
                            "latitude": None,
                            "longitude": None,
                            "lead_score": 0,
                            "category": "Barbershop",
                            "status": "OPERATIONAL",
                            "scraped_at": "",
                            "source": "yelo.ma",
                            "place_id": "",
                        })
                except Exception as e:
                    logger.debug(f"  Error extracting yelo listing: {e}")
                    continue

            if count < 15:
                break

            page_num += 1
            await asyncio.sleep(1)

        except Exception as e:
            logger.debug(f"  Error on yelo page {page_num}: {e}")
            break
        finally:
            await page.close()

    logger.info(f"  yelo.ma: {len(shops)} shops from {city_name}")
    return shops


async def scrape_all_yelo(max_cities: int = 10, max_listings: int = 50) -> list[dict]:
    """Scrape all cities from yelo.ma."""
    from playwright.async_api import async_playwright

    all_shops = []
    cities = MOROCCAN_CITIES[:max_cities]

    logger.info(f"Starting yelo.ma scrape: {len(cities)} cities")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
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
        )

        for i, (city_name, lat, lng, radius) in enumerate(cities):
            logger.info(f"\n[{i+1}/{len(cities)}] {city_name} (yelo.ma)")
            shops = await scrape_yelo_city(city_name, context, max_listings)
            all_shops.extend(shops)

        await browser.close()

    all_shops = deduplicate(all_shops)
    return all_shops


def scrape_all_yelo_sync(max_cities: int = 10, max_listings: int = 50) -> list[dict]:
    """Synchronous wrapper."""
    return asyncio.run(scrape_all_yelo(max_cities, max_listings))
