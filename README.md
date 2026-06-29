# Qutbi Leads Scraper

Moroccan barbershop lead generation tool for Qutbi SaaS outbound sales.
Scrapes Google Maps to find barbershops across Morocco with contact info, ratings, and lead scoring.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Qutbi Leads Scraper                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  scraper/main.py          (CLI entry point)              │   │
│  │  - argparse CLI parsing                                  │   │
│  │  - dispatches to playwright or places_api                │   │
│  └──────────────┬─────────────────────────────┬────────────┘   │
│                 │                             │                 │
│         ┌───────▼────────┐          ┌────────▼───────┐        │
│         │ maps_scraper.py │          │ places_api.py  │        │
│         │ (Playwright)    │          │ (Google API)   │        │
│         │ - headless      │          │ - HTTP/S       │        │
│         │   Chromium      │          │ - structured   │        │
│         │ - free          │          │   data         │        │
│         │ - stealth mode  │          │ - reliable     │        │
│         └───────┬─────────┘          └────────┬───────┘        │
│                 │                             │                 │
│                 └──────────┬──────────────────┘                 │
│                            │                                    │
│                    ┌───────▼────────┐                          │
│                    │   utils.py     │                          │
│                    │ - CSV/JSON     │                          │
│                    │ - dedup        │                          │
│                    │ - lead scoring │                          │
│                    │ - phone fmt    │                          │
│                    └────────────────┘                          │
│                            │                                    │
│                    ┌───────▼────────┐                          │
│                    │   cities.py    │                          │
│                    │ - 20 cities    │                          │
│                    │ - 8 queries    │                          │
│                    └────────────────┘                          │
│                            │                                    │
│                    ┌───────▼────────┐                          │
│                    │   output/      │                          │
│                    │  *.csv / *.json│                          │
│                    └────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
qutbi-leads-scraper/
├── Dockerfile              # Python 3.11-slim + Chromium
├── docker-compose.yml      # 3 services: scraper, quick-test, full-scrape
├── requirements.txt        # requests + playwright
├── .env.example            # GOOGLE_PLACES_API_KEY template
├── .dockerignore
├── scraper/
│   ├── __init__.py         # Makes scraper a package
│   ├── main.py             # CLI entry point (argparse)
│   ├── maps_scraper.py     # Playwright-based Google Maps scraper
│   ├── places_api.py       # Google Places API (New) scraper
│   ├── utils.py            # Output, dedup, scoring, phone formatting
│   └── cities.py           # 20 Moroccan cities + 8 search queries
└── output/                 # Generated CSV/JSON files (gitignored)
```

## Internal Modules

### `scraper/main.py` — CLI Entry Point

Parses CLI args and dispatches to the selected scraper backend.

| Flag | Default | Description |
|------|---------|-------------|
| `--method` | `playwright` | `playwright` or `places_api` |
| `--api-key` | `$GOOGLE_PLACES_API_KEY` | Google Places API key |
| `--headless` | `true` | Run browser headless |
| `--cities` | `10` | Number of cities (max 20) |
| `--max-listings` | `20` | Max listings per query per city |
| `--details` | `false` | Click each listing for phone/website (slower) |
| `--format` | `csv` | `csv`, `json`, or `both` |
| `--output` | auto | Custom output filename |

### `scraper/maps_scraper.py` — Playwright Scraper

Headless Chromium scraper for Google Maps. No API key needed.

**Flow per city:**
1. Opens `https://www.google.com/maps/search/{query}+{city}+morocco/@{lat},{lng},{zoom}z`
2. Dismisses cookie consent popup
3. Waits for `div[role='feed']` results panel
4. Scrolls to load more listings (up to 5 scrolls)
5. Extracts name, rating, review count from each listing card
6. Optionally clicks each listing for detailed data (phone, website)

**Anti-detection:**
- Custom Chrome user-agent
- `fr-MA` locale, Casablanca geolocation
- Removes `navigator.webdriver` flag
- Disables `AutomationControlled` blink feature

**`_extract_phone(text)`** — regex patterns for `+212`, `05-07` Moroccan prefixes.

### `scraper/places_api.py` — Google Places API Scraper

Uses Google Places API (New). Requires a valid API key.

**Endpoint:** `POST https://places.googleapis.com/v1/places:searchText`

**Flow per city:**
1. POSTs `textQuery: "{query} in Morocco"` with `locationBias` circle
2. Paginates up to 3 pages per query
3. Parses response, filters by barbershop-relevant types
4. Respects HTTP 429 rate limits with 10s backoff

**Field mask** requests only: `displayName`, `formattedAddress`, `nationalPhoneNumber`, `internationalPhoneNumber`, `websiteUri`, `rating`, `userRatingCount`, `location`, `id`, `types`, `businessStatus`

### `scraper/utils.py` — Utilities

| Function | Purpose |
|----------|---------|
| `sanitize_phone()` | Normalizes Moroccan numbers to `+212XXXXXXXXX` (E.164) |
| `extract_website()` | Prepends `https://` if missing |
| `score_lead()` | Calculates 1-100 lead score |
| `save_to_csv()` | Writes UTF-8 BOM CSV with all fields |
| `save_to_json()` | Writes indented JSON |
| `deduplicate()` | Deduplicates by name+city and phone |
| `print_summary()` | Console report: totals, % with phone, avg rating, high leads |

### `scraper/cities.py` — Static Data

- **`MOROCCAN_CITIES`**: 20 tuples of `(city, lat, lng, radius_km)` covering major Moroccan cities
- **`SEARCH_QUERIES`**: 8 multilingual queries (EN, FR, AR) for max coverage

## Data Schema

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Barbershop name |
| `address` | string | Full address |
| `city` | string | Moroccan city |
| `phone` | string | Raw phone number |
| `phone_formatted` | string | E.164 formatted (`+212...`) |
| `website` | string | Website URL |
| `rating` | float | Google rating (1-5) |
| `reviews` | int | Number of reviews |
| `latitude` | float | GPS latitude |
| `longitude` | float | GPS longitude |
| `lead_score` | int | 1-100 sales potential score |
| `category` | string | Barbershop / Hair Salon / Beauty Salon |
| `status` | string | OPERATIONAL / CLOSED_PERMANENTLY |
| `scraped_at` | string | ISO 8601 timestamp |
| `source` | string | `google_maps` or `places_api` |
| `place_id` | string | Google Place ID (API method only) |

## Lead Scoring

```
Base score:         50
+ Has phone:       +20
+ Has website:     +10
+ Rating >= 4.0:   +10
+ Rating >= 3.0:    +5
+ Reviews >= 50:   +10
+ Reviews >= 20:    +5
+ Reviews >= 5:     +2
─────────────────────────
Maximum:           100
```

Target leads with **score >= 70** for outreach.

## Quick Start

### Docker (Recommended)

```bash
# Build
docker compose build

# Quick test (1 city, 10 listings)
docker compose run --rm quick-test

# Default scrape (10 cities, CSV + JSON)
docker compose run --rm scraper

# Full 20-city scrape with details
docker compose --profile full run --rm full-scrape

# Custom: 5 cities, 50 listings each, JSON only
docker compose run --rm scraper --cities 5 --max-listings 50 --format json

# Use Places API instead
docker compose run --rm scraper --method places_api --api-key YOUR_KEY
```

### Native Python

```bash
# Setup
python -m venv venv
# Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Run
python -m scraper.main --cities 5 --format csv
python -m scraper.main --method places_api --api-key YOUR_KEY
```

## Two Scraping Methods

| Aspect | Playwright (Default) | Google Places API |
|--------|---------------------|-------------------|
| **Cost** | Free | ~$17/1000 requests |
| **API key** | No | Yes |
| **Speed** | Slower (30-60 min full) | Fast |
| **Reliability** | May hit CAPTCHAs | Robust |
| **Data quality** | Good | Better (structured) |
| **Legal** | Gray area (scraping) | Official API |

## Cities Coverage

Casablanca, Rabat, Marrakech, Fes, Tangier, Agadir, Meknes, Oujda, Kenitra, Tetouan, Sale, Temara, El Jadida, Nador, Beni Mellal, Mohammedia, Khouribga, Settat, Taza, Safi

Search radii: 15km (major cities) to 8km (smaller ones).

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_PLACES_API_KEY` | For `places_api` only | — | Google Places API (New) key |

```bash
cp .env.example .env
# Edit .env with your key
```

## Tips

1. **Start small** — test with `--cities 1` before large scrapes
2. **Use `--details`** — gets more phone numbers but is ~3x slower
3. **Places API for production** — more reliable data, fewer captchas
4. **Deduplication** — automatic by name+city and phone number
5. **Run overnight** — full 20-city Playwright scrape takes 30-60 min
6. **VPN/proxy** — rotate IPs for large Playwright scrapes

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker build fails | Allocate 4GB+ RAM to Docker |
| No results / captcha | Try `--headless false` or switch to Places API |
| Empty phone numbers | Use `--details` flag |
| Rate limited | Reduce cities, add delays, or use Places API |
| Browser crashes | Lower `--max-listings` or reduce city count |

## Tech Stack

- **Python 3.11** — slim Docker image
- **Playwright** — Chromium browser automation
- **Google Places API (New)** — optional production backend
- **Docker + Compose** — containerized deployment
- **CSV/JSON** — output formats with UTF-8 BOM
