# Weather Tracker API

A Django REST Framework API that tracks live weather data across all 27 governorate capitals of Egypt, with JWT authentication, per-user favorites, threshold-based email alerts, AI-generated insights and forecasts, and Excel export — built on Postgres, Redis, and Celery.

---

## Features

- **Automated data collection** — Celery Beat triggers an hourly fetch from the [Open-Meteo](https://open-meteo.com/) API for all 27 tracked cities, storing each reading as a `WeatherRecord`.
- **JWT authentication** — public read access; write actions (update, delete, export, AI endpoints) require a logged-in user. Open registration.
- **City filtering** — `GET /api/weather/?city=<name>` filters records server-side.
- **Computed temperature difference** — each record shows its change vs. the previous reading for that city, computed live (never stored, so it can't go stale).
- **Favorites** — authenticated users can save cities they care about (`FavoriteCity`), enforced unique per user via a database constraint.
- **Excel export** — `GET /api/weather/export/` streams a real `.xlsx` file of all records, rate-limited to 5/hour.
- **AI-powered endpoints** (Google Gemini):
  - `insights` — plain-language trend summary, suggested activities, safety warnings, and anomaly detection against a 7-day rolling average.
  - `forecast` — real 3-day forecast data from Open-Meteo, narrated in plain language (the AI never invents the numbers — it only explains real forecast data).
  - `ask` — free-text natural language questions (e.g. *"What's the hottest city right now?"*) answered against real database queries. The AI only decides *what* to look up (city/metric/aggregation, from a fixed set of valid options); the actual computation always happens in Django, never in the AI response.
- **Threshold email alerts** — proof-of-concept: the Celery task sends an email when a fetched temperature exceeds a set threshold (see [Known Limitations](#known-limitations)).
- **Swagger / OpenAPI docs** — full interactive API documentation at `/api/docs/`.
- **Rate limiting** on the export endpoint via DRF throttling.
- **Dockerized** — Redis, Django (via Gunicorn), Celery worker, and Celery Beat each run as separate services; Postgres runs natively/externally.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django + Django REST Framework |
| Database | PostgreSQL |
| Background tasks | Celery |
| Message broker | Redis |
| Scheduling | Celery Beat |
| Auth | JWT (`djangorestframework-simplejwt`) |
| AI | Google Gemini (`google-generativeai`) |
| Docs | drf-spectacular (Swagger/OpenAPI) |
| Export | openpyxl |
| Web server (prod) | Gunicorn |
| Containerization | Docker + Docker Compose |
| Testing | pytest, pytest-django, pytest-cov |

---

## Project Structure

```
weather_tracker/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
├── weather/
│   ├── models.py          # WeatherRecord, FavoriteCity
│   ├── serializers.py
│   ├── views.py            # WeatherViewSet, FavoriteCityViewSet, RegisterView
│   ├── urls.py
│   ├── tasks.py             # fetch_weather_data (Celery task)
│   ├── conftest.py          # pytest fixtures
│   └── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── .env                     # not committed — see Environment Variables
└── postman/
    ├── weather_tracker.postman_collection.json
    └── weather_tracker.postman_environment.json
```

---

## Environment Variables

Create a `.env` file at the project root (never commit this):

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
GEMINI_API_KEY=your-gemini-api-key
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).

---

## Getting Started (local, without Docker)

```bash
python -m venv venv
source venv/bin/activate        # or venv\Scripts\activate on Windows

pip install -r requirements.txt

# Postgres must be running natively; create the database first:
#   CREATE DATABASE weather_db;

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

In separate terminals, also run:
```bash
celery -A config worker --loglevel=info --pool=solo   # --pool=solo needed on Windows
celery -A config beat --loglevel=info
```

Redis must be running (`docker run -d -p 6379:6379 redis` is the simplest option on Windows, since there's no official native Redis build for Windows).

---

## Getting Started (Docker)

Postgres runs natively/externally, not inside Compose — set `HOST` in `settings.py`'s `DATABASES` to `host.docker.internal` (Docker Desktop's DNS name for the host machine).

```bash
docker-compose up --build
```

This starts Redis, the Django app (via Gunicorn), the Celery worker, and Celery Beat as four separate containers.

---

## API Overview

Full interactive documentation: `GET /api/docs/`

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/register/` | POST | Public | Create an account |
| `/api/token/` | POST | Public | Log in, get JWT tokens |
| `/api/token/refresh/` | POST | Public | Refresh an access token |
| `/api/weather/` | GET | Public | List records (supports `?city=`) |
| `/api/weather/<id>/` | GET | Public | Retrieve one record |
| `/api/weather/<id>/` | PATCH/PUT | Auth | Update a record |
| `/api/weather/<id>/` | DELETE | Auth | Delete a record |
| `/api/weather/` | POST | — | Not available — records are only created by the scheduled fetch |
| `/api/weather/insights/?city=` | GET | Auth | AI trend summary, activities, warnings, anomaly detection |
| `/api/weather/forecast/?city=` | GET | Auth | Real 3-day forecast, AI-narrated |
| `/api/weather/ask/` | POST | Auth | Natural-language question answering |
| `/api/weather/export/` | GET | Auth | Download all records as `.xlsx` (5/hour limit) |
| `/api/favorite-cities/` | GET/POST | Auth | List / create favorites |
| `/api/favorite-cities/<id>/` | DELETE | Auth | Remove a favorite |

A ready-to-import Postman collection and environment are in `/postman`.

---

## Design Decisions Worth Knowing

- **`temperature_diff` is computed, not stored** — calculated live in the serializer by querying the previous record for that city, so it can never go stale if records are edited or deleted.
- **Reading is public, writing is gated** — mirrors how the underlying data is genuinely public (same as Open-Meteo itself), while mutations require an accountable user.
- **The AI never invents numbers** — every AI endpoint is fed real, already-computed data (recent readings, 7-day averages, or real forecast data) and is only asked to *interpret or narrate* it, never to generate the underlying figures itself.
- **`ask` never lets the AI query the database directly** — the AI only selects from a small, fixed, validated set of parameters (city, metric, aggregation). Django always performs the actual query. Any AI response outside the supported shape is rejected before it reaches the database layer.
- **Celery Beat and the worker are independent, always-running processes** — like the Django dev server, they don't start automatically; each needs to be running for the automated pipeline to work.

---

## Testing

```bash
pytest --cov=weather --cov-report=term-missing --cov-report=html
```

Current coverage: **96%**.

**What's covered:**
- Public vs. authenticated access on all `WeatherRecord` actions
- `temperature_diff` computation (including the no-previous-record case)
- Favorites: creation, ownership isolation, duplicate prevention, missing Update action
- `ask` endpoint validation boundaries (unsupported questions, invalid AI output, and a regression test for a real bug found during test-writing — see below)
- `fetch_weather_data` (the Celery task): correct record creation per city, correct field mapping from the API response, timezone-aware timestamps, and that one city's API failure doesn't stop other cities from being processed
- `insights` and `forecast`: successful responses, missing/unknown city handling, and malformed/empty AI response handling
- All external calls (Gemini, Open-Meteo) are mocked in tests — no real network calls or API costs are incurred by running the test suite

**A real bug found via testing:** writing tests for `ask` surfaced an `UnboundLocalError` that only occurred on the `aggregation: "latest"` branch — a variable was defined inside one conditional branch but used after both branches merged, so it worked for every case manually tested (`max`, `avg`) but crashed on the one untested branch (`latest`). Fixed, and now covered by a dedicated regression test.
