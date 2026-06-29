# Qutbi Leads Scraper — Agent Guide

## Overview

Single-package Python CLI tool (`scraper/`) that generates barbershop leads in Morocco by scraping Google Maps. Two backends: Playwright (free, browser-based) and Google Places API (paid, reliable).

## Code Conventions

- **Format**: No formatter configured — match existing style (4-space indent, single quotes for strings where possible)
- **Types**: Minimal typing — `Optional[str]` and `list[dict]` used sparingly
- **Logging**: `logging.getLogger(__name__)` with `logger.info/warning/error`
- **Async**: Playwright uses `asyncio`; Places API is synchronous with `requests`
- **Imports**: Standard library first, then third-party, then local — no blank lines between groups

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Playwright over Selenium | Modern API, native async, better selector engine |
| Places API (New) over legacy | Simpler field-mask-based response, no API key restrictions per method |
| 3 queries per city max | Prevents rate limits while still getting multi-language coverage |
| `div[role='feed']` selector | Google Maps results panel — stable across page layouts |
| UTF-8 BOM for CSV | Ensures French/Arabic characters display correctly in Excel |

## Common Tasks

### Add a new city
Edit `scraper/cities.py` — add a `(name, lat, lng, radius_km)` tuple to `MOROCCAN_CITIES`. Keep radius between 8-15km.

### Add a search query
Edit `scraper/cities.py` — append a new string to `SEARCH_QUERIES`. The first 3 queries are used by default; `--details` or full scrape uses all 8.

### Add a new output field
1. Add the field to `shop` dicts created in `maps_scraper.py` and/or `places_api.py`
2. Add to `fieldnames` list in `utils.py:save_to_csv()`
3. Add to `save_to_json()` if needed

### Modify lead scoring
Edit `utils.py:score_lead()` — adjust point values. Keep max at 100.

### Fix phone extraction for a new country
1. Edit `maps_scraper.py:_extract_phone()` — add new regex patterns
2. Edit `utils.py:sanitize_phone()` — add country code normalization

### Debug Playwright scraping
Run locally: `python -m scraper.main --headless false --cities 1`. The visible browser shows what Google Maps returns.

## Testing

No test framework is configured. Manual testing via Docker:

```bash
docker compose run --rm quick-test
cat output/*.csv
```

## Deployment

Single-container Docker app. Output directory mounts to host. No CI/CD configured.

## Dependencies

- `playwright>=1.45.0` — browser automation (required)
- `requests>=2.31.0` — HTTP for Places API (only needed with `--method places_api`)
