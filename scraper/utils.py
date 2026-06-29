"""Utility functions for the scraper."""

import csv
import json
import os
import re
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def sanitize_phone(phone: str) -> Optional[str]:
    """Clean and normalize a phone number to E.164 format for Morocco."""
    if not phone:
        return None
    # Remove all non-digit characters
    digits = re.sub(r"[^\d+]", "", phone.strip())
    # Morocco country code normalization
    if digits.startswith("+212"):
        return digits
    elif digits.startswith("00212"):
        return "+212" + digits[5:]
    elif digits.startswith("06") or digits.startswith("07"):
        return "+212" + digits[1:]
    elif digits.startswith("212"):
        return "+" + digits
    return phone if digits else None


def extract_website(url: str) -> Optional[str]:
    """Ensure URL has a protocol."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("http"):
        return url
    return f"https://{url}"


def score_lead(shop: dict) -> int:
    """Score a lead from 1-100 based on sales potential."""
    score = 50  # base score

    # Has phone number = very important
    if shop.get("phone"):
        score += 20

    # Has website = established business
    if shop.get("website"):
        score += 10

    # Rating signals quality
    rating = shop.get("rating", 0) or 0
    if rating >= 4.0:
        score += 10
    elif rating >= 3.0:
        score += 5

    # Review count signals active business
    reviews = shop.get("reviews", 0) or 0
    if reviews >= 50:
        score += 10
    elif reviews >= 20:
        score += 5
    elif reviews >= 5:
        score += 2

    return min(score, 100)


def save_to_csv(shops: list[dict], filename: Optional[str] = None) -> str:
    """Save shop data to a CSV file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"barbershops_morocco_{timestamp}.csv"

    filepath = os.path.join(OUTPUT_DIR, filename)

    fieldnames = [
        "name",
        "address",
        "city",
        "phone",
        "phone_formatted",
        "website",
        "rating",
        "reviews",
        "latitude",
        "longitude",
        "lead_score",
        "category",
        "status",
        "scraped_at",
        "source",
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for shop in shops:
            shop["phone_formatted"] = sanitize_phone(shop.get("phone"))
            shop["website"] = extract_website(shop.get("website"))
            shop["lead_score"] = score_lead(shop)
            shop["scraped_at"] = datetime.now().isoformat()
            writer.writerow(shop)

    logger.info(f"Saved {len(shops)} shops to {filepath}")
    return filepath


def save_to_json(shops: list[dict], filename: Optional[str] = None) -> str:
    """Save shop data to a JSON file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"barbershops_morocco_{timestamp}.json"

    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(shops)} shops to {filepath}")
    return filepath


def deduplicate(shops: list[dict]) -> list[dict]:
    """Remove duplicate shops by name+city or phone."""
    seen = set()
    unique = []
    for shop in shops:
        name = (shop.get("name") or "").lower().strip()
        city = (shop.get("city") or "").lower().strip()
        phone = sanitize_phone(shop.get("phone")) or ""

        key1 = f"{name}|{city}"
        key2 = f"phone:{phone}" if phone else ""

        if key1 not in seen and (not key2 or key2 not in seen):
            seen.add(key1)
            if key2:
                seen.add(key2)
            unique.append(shop)

    removed = len(shops) - len(unique)
    if removed > 0:
        logger.info(f"Removed {removed} duplicate shops")

    return unique


def print_summary(shops: list[dict]):
    """Print a summary of scraped data."""
    if not shops:
        print("\n[!] No shops found.")
        return

    cities_count = len(set(s.get("city", "") for s in shops))
    with_phone = sum(1 for s in shops if s.get("phone"))
    with_website = sum(1 for s in shops if s.get("website"))
    with_rating = sum(1 for s in shops if s.get("rating"))
    avg_rating = sum(s.get("rating", 0) or 0 for s in shops) / max(with_rating, 1)
    high_leads = sum(1 for s in shops if score_lead(s) >= 70)

    print("\n" + "=" * 60)
    print(f"  SCRAPING SUMMARY")
    print("=" * 60)
    print(f"  Total shops found     : {len(shops)}")
    print(f"  Cities covered        : {cities_count}")
    print(f"  With phone number     : {with_phone} ({with_phone*100//max(len(shops),1)}%)")
    print(f"  With website          : {with_website} ({with_website*100//max(len(shops),1)}%)")
    print(f"  With rating           : {with_rating}")
    print(f"  Average rating        : {avg_rating:.1f}")
    print(f"  High-quality leads    : {high_leads} (score >= 70)")
    print("=" * 60)