# Errand Planner (Calendar + Places Scheduler)

An intelligent errand scheduling system that builds an order of errands by considering:
- Your Google Calendar availability (free time slots)
- Business/places hours (fetched from Google Places details when available)
- Travel time + distance (Google Maps Distance Matrix, with haversine fallback)
- Buffer time between stops

The UI then shows:
- A **week-at-a-glance schedule** page with both your **calendar events** and the **scheduled errands**.

## Features
- **Calendar integration**: Reads your Google Calendar events for a selected window.
- **Places autocomplete**: Search businesses/stores and select a `place_id`.
- **Hours-aware scheduling**: Uses Google place hours when possible; otherwise falls back to the user’s scheduling window.
- **Overnight hours support**: Handles places open across midnight (e.g. `9:00 AM – 2:00 AM`).
- **Modern UI**: Airbnb-inspired layout with dropdown autocomplete and a dedicated schedule view (`schedule.html`).

## Project Layout
- `backend.py`: FastAPI backend (autocomplete, scheduling, reverse geocoding)
- `frontend.js`: Frontend logic for adding errands and requesting a schedule
- `index.html`: Main UI
- `schedule.html`: Weekly schedule display page
- `errand_resolution.py`: Core scheduling logic + Google Maps client
- `calendar_scraper.py`: Google Calendar OAuth + event fetching

## Local Setup

### 1) Create a virtual environment + install dependencies
From the project folder:

```bash
python -m venv venv
venv\Scripts\activate

pip install fastapi uvicorn google-api-python-client google-auth google-auth-oauthlib googlemaps
```

### 2) Google Maps API key via `.env`
This project expects `GOOGLE_MAPS_API_KEY` in a local `.env`.

1. Copy the example file:
   - `cp .env.example .env` (or create it manually on Windows)
2. Set:
   - `GOOGLE_MAPS_API_KEY=your_key_here`

The repo includes `.gitignore` to prevent committing secrets.

### 3) Google Calendar OAuth credentials
1. Download Google Calendar API `credentials.json`
2. Place it in the project root as `credentials.json`
3. On first run, the backend will open an OAuth flow and create `token.json`

Notes:
- `token.json` is sensitive and is ignored by git (see `.gitignore`).

## Run Locally

### Run the backend (FastAPI)
```bash
python backend.py
```
Open:
- API docs: http://127.0.0.1:8000/docs

### Run the frontend (static files)
In another terminal:
```bash
python -m http.server 5500 --bind 127.0.0.1
```
Open:
- Main page: http://127.0.0.1:5500/index.html
- Schedule page: `schedule.html` (you’ll typically navigate here after generating a schedule)

## How to Use
1. On `index.html`, fill in:
   - **Home address** (or toggle **Use current location**)
   - **Start** / **End** date-times for the scheduling window
2. Add errands using **Search for a place**:
   - Select a dropdown result (this is what provides `place_id` and enables hours lookup)
   - Enter **duration (minutes)**
   - Click **Add errand**
3. Click **Generate schedule**
4. You’ll be redirected to `schedule.html` where you can see:
   - Calendar events by day/time
   - Scheduled errands by day/time

## Security / Git Hygiene
The project includes a `.gitignore` that ignores:
- `.env` (API keys)
- `credentials.json` and `token.json` (OAuth secrets)
- `venv/` and other local artifacts


