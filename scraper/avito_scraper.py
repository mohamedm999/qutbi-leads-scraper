"""Scraper for Avito.ma — extracts Moroccan barber phone numbers.

Uses national search to avoid Cloudflare blocks on city pages.
"""

import asyncio
import logging
import re

from .utils import sanitize_phone

logger = logging.getLogger(__name__)


def _extract_phones(html: str) -> set:
    phones = set()
    for m in re.finditer(r'0[5-7]\d{8}', html):
        p = sanitize_phone(m.group(0))
        if p:
            phones.add(p)
    return phones


async def scrape_all_avito(max_cities: int = 10, max_listings: int = 50) -> list[dict]:
    from playwright.async_api import async_playwright

    logger.info('Starting Avito.ma scrape (national search)')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            locale='fr-FR',
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        page = await context.new_page()
        all_phones = set()

        for query in ['coiffeur', 'barber']:
            if len(all_phones) >= max_listings * max_cities:
                break
            for page_num in range(1, 4):
                if len(all_phones) >= max_listings * max_cities:
                    break
                url = f'https://www.avito.ma/fr/maroc/{query}'
                if page_num > 1:
                    url += f'?page={page_num}'
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    await page.wait_for_timeout(3000)
                    body = await page.locator('body').inner_text()
                    if any(k in body for k in ['Just a moment', 'vérification', 'Cloudflare']):
                        logger.warning(f'  Cloudflare block on {query} page {page_num}')
                        continue
                    html = await page.content()
                    phones = _extract_phones(html)
                    logger.info(f'  {query} page {page_num}: {len(phones)} phones')
                    all_phones.update(phones)
                except Exception as e:
                    logger.debug(f'  Error on {url}: {e}')

        await browser.close()

    shops = []
    for phone in list(all_phones)[:max_listings * max_cities]:
        shops.append({
            'name': '', 'address': '', 'city': '',
            'phone': phone, 'phone_formatted': phone,
            'website': '', 'rating': None, 'reviews': None,
            'latitude': None, 'longitude': None,
            'lead_score': 70, 'category': 'Barbershop',
            'status': 'OPERATIONAL', 'scraped_at': '',
            'source': 'avito.ma', 'place_id': '',
        })

    logger.info(f'Avito total: {len(shops)} unique phones from national search')
    return shops


def scrape_all_avito_sync(max_cities: int = 10, max_listings: int = 50) -> list[dict]:
    return asyncio.run(scrape_all_avito(max_cities, max_listings))
