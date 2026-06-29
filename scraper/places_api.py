"""Google Places API scraper for Moroccan barbershops.

This method uses the official Google Places API (New) and requires an API key.
It's the most reliable and legal approach.

Get your API key: https://console.cloud.google.com/apis/credentials
Enable: Places API (New)
"""

import time
import logging
from typing import Optional

import requests

from .cities import MOROCCAN_CITIES, SEARCH_QUERIES
from .utils import deduplicate

logger = logging.getLogger(__name__)

PLACES_API_BASE = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_BASE = "https://places.googleapis.com/v1/places/{place_id}"

# Fields we want from the search
SEARCH_FIELDS = [
    "displayName",
    "formattedAddress",
    "nationalPhoneNumber",
    "internationalPhoneNumber",
    "websiteUri",
    "rating",
    "userRatingCount",
    "location",
    "id",
    "types",
    "businessStatus",
]

DETAIL_FIELDS = [
    "displayName",
    "formattedAddress",
    "nationalPhoneNumber",
    "internationalPhoneNumber",
    "websiteUri",
    "rating",
    "userRatingCount",
    "location",
    "types",
    "businessStatus",
    "regularOpeningHours",
]


def _make_headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(SEARCH_FIELDS),
    }


def _extract_city_from_address(address: str) -> str:
    """Try to extract city name from a formatted address."""
    parts = address.split(",")
    for part in parts:
        stripped = part.strip().lower()
        # Known Moroccan cities
        known = [c[0].lower() for c in MOROCCAN_CITIES]
        for city in known:
            if city in stripped:
                return city.title()
    # Return second-to-last part as a guess
    if len(parts) >= 2:
        return parts[-2].strip().title()
    return ""


def search_place(
    query: str,
    lat: float,
    lng: float,
    radius: int,
    api_key: str,
    next_page_token: Optional[str] = None,
) -> dict:
    """Search for places using Google Places API (New)."""
    headers = _make_headers(api_key)

    body = {
        "textQuery": f"{query} in Morocco",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius * 1000,  # km to meters
            }
        },
        "pageSize": 20,
        "languageCode": "fr",
    }

    if next_page_token:
        body["pageToken"] = next_page_token

    resp = requests.post(PLACES_API_BASE, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_place(place: dict, search_city: str) -> dict:
    """Parse a Place API response into our standard format."""
    name = place.get("displayName", {}).get("text", "")
    address = place.get("formattedAddress", "")
    phone = (
        place.get("internationalPhoneNumber")
        or place.get("nationalPhoneNumber")
        or ""
    )
    website = place.get("websiteUri", "")
    rating = place.get("rating")
    reviews = place.get("userRatingCount")
    location = place.get("location", {})
    lat = location.get("latitude")
    lng = location.get("longitude")
    place_id = place.get("id", "")
    types = place.get("types", [])
    status = place.get("businessStatus", "OPERATIONAL")

    # Filter for barbershop-related types
    barber_keywords = [
        "barber",
        "hair_salon",
        "hair_care",
        "beauty_salon",
        "health",
        "establishment",
        "point_of_interest",
    ]
    is_barber = any(t in barber_keywords for t in types) if types else True

    category = "Barbershop"
    if "hair_salon" in (types or []):
        category = "Hair Salon"
    if "beauty_salon" in (types or []):
        category = "Beauty Salon"

    return {
        "name": name,
        "address": address,
        "city": _extract_city_from_address(address) or search_city,
        "phone": phone,
        "website": website,
        "rating": rating,
        "reviews": reviews,
        "latitude": lat,
        "longitude": lng,
        "place_id": place_id,
        "category": category,
        "status": status,
        "source": "places_api",
        "_is_barber": is_barber,
    }


def scrape_city(
    city_name: str,
    lat: float,
    lng: float,
    radius: int,
    api_key: str,
    queries: Optional[list[str]] = None,
) -> list[dict]:
    """Scrape all barbershops for a single city."""
    shops = []
    queries = queries or SEARCH_QUERIES[:3]  # Limit queries to avoid rate limits

    for query in queries:
        logger.info(f"  Searching: '{query}' in {city_name}")
        page_token = None
        page_num = 0

        while True:
            try:
                result = search_place(query, lat, lng, radius, api_key, page_token)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logger.warning(f"  Rate limited. Waiting 10s...")
                    time.sleep(10)
                    continue
                logger.error(f"  API error: {e}")
                break
            except Exception as e:
                logger.error(f"  Error: {e}")
                break

            places = result.get("places", [])
            for place in places:
                shop = parse_place(place, city_name)
                if shop["_is_barber"]:
                    shops.append(shop)

            page_token = result.get("nextPageToken")
            page_num += 1

            if not page_token or page_num >= 3:  # Max 3 pages per query
                break

            time.sleep(2)  # Rate limit between pages

        time.sleep(1)  # Rate limit between queries

    return shops


def scrape_all(api_key: str, max_cities: int = 20) -> list[dict]:
    """Scrape barbershops across all Moroccan cities."""
    all_shops = []
    cities = MOROCCAN_CITIES[:max_cities]

    logger.info(f"Starting Places API scrape for {len(cities)} cities...")

    for i, (city_name, lat, lng, radius) in enumerate(cities):
        logger.info(f"\n[{i+1}/{len(cities)}] {city_name}")
        shops = scrape_city(city_name, lat, lng, radius, api_key)
        all_shops.extend(shops)
        logger.info(f"  Found {len(shops)} shops")
        time.sleep(1)

    # Deduplicate
    all_shops = deduplicate(all_shops)

    return all_shops