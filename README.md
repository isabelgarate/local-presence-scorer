# Local Presence Scorer

Score, rank and compare local businesses' digital presence using **Google Business Profile** and **Instagram** data.

Built for SMBs and agencies that want to benchmark digital visibility and generate actionable improvement recommendations.

---

## Scoring model

```
total_score = 0.50 × local_score + 0.35 × social_score + 0.15 × activity_score
```

### Local score (Google Business Profile)
```
local_score =
  0.35 × normalized_rating
  0.30 × normalized_review_count      (log scale, cap: 500)
  0.15 × category_match
  0.10 × website_present
  0.10 × profile_completeness
```

### Social score (Instagram)
```
social_score = 0.50 × followers + 0.50 × engagement_rate
```

### Activity score (Instagram)
```
activity_score = 0.60 × posts_last_30d + 0.40 × reels_last_30d
```

Grades: **A** (≥0.80) · **B** (≥0.65) · **C** (≥0.50) · **D** (≥0.35) · **F** (<0.35)

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/local-presence-scorer
cd local-presence-scorer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your keys
```

Required:
- **`GOOGLE_PLACES_API_KEY`** — [Google Cloud Console](https://console.cloud.google.com/) → Enable *Places API (New)*
- **`RAPIDAPI_KEY`** — [RapidAPI](https://rapidapi.com/) → Subscribe to *instagram-api-fast-reliable-data-scraper* (Phase 2, optional)

### 3. Run the API

```bash
uvicorn local_scorer.api.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

### 4. Use the CLI

```bash
# Search businesses (local score only, fast)
local-scorer search "restaurante italiano" --location "Madrid"

# Full score with recommendations
local-scorer score "La Trattoria" --location "Madrid"

# Compare and rank multiple businesses
local-scorer compare "La Trattoria" "Ristorante Roma" "Il Forno" --location "Madrid"

# JSON output for piping
local-scorer score "La Trattoria" --location "Madrid" --json
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Service status |
| `POST` | `/api/v1/search` | Find businesses by type + location (local score) |
| `POST` | `/api/v1/score` | Full score for a single business |
| `POST` | `/api/v1/compare` | Rank multiple businesses side by side |

### Example: Score a business

```bash
curl -X POST http://localhost:8000/api/v1/score \
  -H "Content-Type: application/json" \
  -d '{"name": "La Trattoria", "location": "Madrid", "include_instagram": false}'
```

Response:
```json
{
  "profile": { "place_id": "ChIJ...", "name": "La Trattoria", "rating": 4.6, ... },
  "score": {
    "total": 0.7812,
    "grade": "B",
    "local_score": { "total": 0.7812, "rating_component": 0.9, ... },
    "social_score": null
  },
  "recommendations": [
    {
      "area": "reviews",
      "priority": "high",
      "title": "Grow your review count",
      "impact_estimate": "+up to 15 pts on local score"
    }
  ]
}
```

---

## Instagram resolution

The tool automatically finds Instagram handles using a tiered approach:

1. **Google Places social links** — instant if the business has linked their Instagram in GBP
2. **Website scrape** — parses `<a>` tags, JSON-LD `sameAs`, and meta tags (~70% hit rate)
3. **Name heuristic** — slugifies the business name as a fallback (low confidence, validated via API)

Set `include_instagram: false` to skip and use local score only.

---

## Development

```bash
# Run tests
pytest

# Run only unit tests (no API keys needed)
pytest tests/unit/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

---

## Roadmap

- [x] **Phase 1** — Google Business Profile scoring
- [x] **Phase 2** — Instagram social + activity scoring
- [ ] **Phase 3** — Web analysis (broken links, SEO keywords, Core Web Vitals)
- [ ] **Phase 4** — AI visibility index (AI Overviews presence, entity clarity, schema markup)

---

## License

MIT
