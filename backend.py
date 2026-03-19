"""Example script demonstrating how to use the errand scheduler."""

# backend.py
import math
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
from pydantic import BaseModel
from googleapiclient.http import HttpError
import uvicorn

from errand_resolution import geocode_address, gmaps, print_scheduled_errands, schedule_errands, Errand
from calendar_scraper import get_credentials, fetch_events_in_range, get_calendar_timezone
from googleapiclient.discovery import build
import datetime
from zoneinfo import ZoneInfo


def _parse_12h_to_24h(time_str: str) -> Optional[tuple]:
    """Parse '9:00 AM' or '5:30 PM' to (hour, minute) 24h. Returns None on failure."""
    time_str = time_str.strip().upper()
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_str)
    if not match:
        return None
    h, m, period = int(match.group(1)), int(match.group(2)), match.group(3)
    if h == 12:
        h = 0
    if period == "PM":
        h += 12
    return (h, m)


def get_place_business_hours(place_id: str) -> Optional[Dict[str, str]]:
    """
    Fetch business hours for a place from Google Place Details.
    Returns dict like {"monday": "9:00-17:00", ...} or None if not available.
    """
    if not place_id:
        return None
    try:
        result = gmaps.place(place_id, fields=["opening_hours"])
        result = result.get("result", {})
        hours = result.get("opening_hours") or result.get("openingHours")
        if not hours:
            return None
        weekday_text = hours.get("weekday_text") or hours.get("weekdayText") or []
        if not weekday_text:
            return None
        out = {}
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for line in weekday_text:
            line = line.strip()
            colon = line.find(":")
            if colon < 0:
                continue
            day_label = line[:colon].strip().lower()
            rest = line[colon + 1:].strip()
            day_key = None
            for d in day_names:
                if d.startswith(day_label[:2]) or day_label == d:
                    day_key = d
                    break
            if not day_key:
                continue
            if rest.lower() in ("closed", ""):
                out[day_key] = "closed"
                continue
            parts = re.split(r"\s*[–\-—]\s*", rest, maxsplit=1)
            if len(parts) != 2:
                out[day_key] = "closed"
                continue
            open_hm = _parse_12h_to_24h(parts[0])
            close_hm = _parse_12h_to_24h(parts[1])
            if open_hm is None or close_hm is None:
                out[day_key] = "closed"
                continue
            oh, om = open_hm
            ch, cm = close_hm
            if (ch, cm) == (0, 0):
                ch, cm = 24, 0
            out[day_key] = f"{oh:02d}:{om:02d}-{ch:02d}:{cm:02d}"
        for d in day_names:
            if d not in out:
                out[d] = "closed"
        return out if out else None
    except Exception as e:
        print(f"Could not fetch place hours for {place_id}: {e}")
        return None


def business_hours_from_window(
    start_dt: datetime.datetime, end_dt: datetime.datetime
) -> Dict[str, str]:
    """Build business_hours from scheduling window: every day open from start time to end time."""
    start_t = start_dt.time()
    end_t = end_dt.time()
    start_str = f"{start_t.hour:02d}:{start_t.minute:02d}"
    end_str = f"{end_t.hour:02d}:{end_t.minute:02d}"
    if end_t.hour == 0 and end_t.minute == 0:
        end_str = "24:00"
    slot = f"{start_str}-{end_str}"
    return {d: slot for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}


def _haversine_km(origin, dest) -> float:
    """Compute great-circle distance in km between two (lat, lon) points."""
    lat1, lon1 = origin
    lat2, lon2 = dest
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


app = FastAPI()
# Enable CORS so the HTML can talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/reverse_geocode")
async def reverse_geocode(lat: float, lng: float):
    """Reverse geocode coordinates to a human-readable address."""
    try:
        results = gmaps.reverse_geocode((lat, lng))
        if not results:
            return {"address": None}
        address = results[0].get("formatted_address")
        return {"address": address}
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return {"address": None, "error": str(e)}

def create_example_errands():
    """Create example errands with coordinates directly."""
    errands = [
        Errand(
            name="Trader Joe's",
            coordinates=None,
            business_hours={
                "monday": "9:00-21:00",
                "tuesday": "9:00-21:00",
                "wednesday": "9:00-21:00",
                "thursday": "9:00-21:00",
                "friday": "9:00-21:00",
                "saturday": "9:00-21:00",
                "sunday": "9:00-21:00",
            },
            duration_minutes=40,
            address="2310 Homestead Rd, Los Altos, CA 94024",  # Optional, for display
        ),
        Errand(
            name="Safeway",
            coordinates=(37.336524, -122.034668),  # Safeway in Cupertino
            business_hours={
                "monday": "5:00-23:59",
                "tuesday": "5:00-23:59",
                "wednesday": "5:00-23:59",
                "thursday": "5:00-23:59",
                "friday": "5:00-23:59",
                "saturday": "5:00-23:59",
                "sunday": "5:00-23:59",
            },
            duration_minutes=20,
            address="Safeway, Cupertino, CA",
        ),
        Errand(
            name="Goodwill",
            coordinates=(37.376492, -122.029406),  # Goodwill in Sunnyvale
            business_hours={
                "monday": "10:00-20:00",
                "tuesday": "10:00-20:00",
                "wednesday": "10:00-20:00",
                "thursday": "10:00-20:00",
                "friday": "10:00-20:00",
                "saturday": "10:00-20:00",
                "sunday": "10:00-20:00",
            },
            duration_minutes=60,
            address="Goodwill, Sunnyvale, CA",
        ),
    ]
    
    return errands

class ErrandInput(BaseModel):
    """Request payload for one errand; business_hours are resolved on the server."""
    name: str
    address: str
    duration_minutes: int
    place_id: Optional[str] = None
    coordinates: Optional[List[float]] = None
    business_hours: Optional[Dict[str, str]] = None


class ScheduleRequest(BaseModel):
    home_address: str
    start_date: str
    end_date: str
    buffer_minutes: int
    errands: List[ErrandInput]

@app.get("/api/autocomplete")
async def autocomplete_places(
    query: str = Query(..., min_length=2),
    home_address: Optional[str] = Query(None),
):
    """
    Autocomplete for businesses/places by name.
    Example: "whole foods" returns all Whole Foods locations
    """
    try:
        # Use places_autocomplete with 'establishment' type
        predictions = gmaps.places_autocomplete(
            input_text=query,
            types='establishment'  # Businesses, stores, restaurants, etc.
        )
        
        suggestions = []
        for place in predictions:
            # Get more details about each place
            place_details = gmaps.place(
                place["place_id"],
                fields=["name", "formatted_address", "geometry", "rating"],
            )
            result = place_details.get("result", {})

            suggestions.append(
                {
                    "name": result.get(
                        "name", place["structured_formatting"].get("main_text")
                    ),
                    "address": result.get("formatted_address", place["description"]),
                    "place_id": place["place_id"],
                    "location": result.get("geometry", {}).get("location", {}),
                    "rating": result.get("rating"),
                }
            )

        # If we have a home address, sort suggestions by distance to it
        if home_address:
            home_coords = geocode_address(home_address)
            if home_coords and home_coords[0] is not None and home_coords[1] is not None:
                def sort_key(s: Dict[str, Dict]) -> float:
                    loc = s.get("location") or {}
                    lat = loc.get("lat")
                    lng = loc.get("lng")
                    if lat is None or lng is None:
                        return float("inf")
                    return _haversine_km(home_coords, (lat, lng))

                suggestions.sort(key=sort_key)

        return {"suggestions": suggestions}
        
    except Exception as e:
        print(f"Autocomplete error: {e}")
        return {'suggestions': [], 'error': str(e)}
        
@app.post("/api/schedule")
async def create_schedule(request: ScheduleRequest):
    """Main function to schedule errands. Business hours are fetched from Google or derived from the scheduling window."""
    print("Authenticating with Google Calendar...")
    creds = get_credentials()

    try:
        service = build("calendar", "v3", credentials=creds)
        calendar_timezone = get_calendar_timezone(service)

        # Use the user's scheduling window
        start_date = datetime.datetime.fromisoformat(
            request.start_date.replace("Z", "+00:00")
        )
        end_date = datetime.datetime.fromisoformat(
            request.end_date.replace("Z", "+00:00")
        )
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=ZoneInfo(calendar_timezone))
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=ZoneInfo(calendar_timezone))

        # Never schedule in the past: clamp window start to "now" in calendar tz
        now_tz = datetime.datetime.now(ZoneInfo(calendar_timezone))
        if start_date < now_tz:
            start_date = now_tz
        if end_date <= start_date:
            raise HTTPException(
                status_code=400, detail="End date must be after current time"
            )

        print(f"\nFetching calendar events from {start_date.date()} to {end_date.date()}...")
        events = fetch_events_in_range(service, start_date, end_date)
        print(f"Found {len(events)} events in calendar")

        errands = []
        for e in request.errands:
            # Resolve business hours: from Google Place Details, or from scheduling window
            hours = e.business_hours
            if not hours and e.place_id:
                hours = get_place_business_hours(e.place_id)
            if not hours:
                hours = business_hours_from_window(start_date, end_date)
                print(f"  No place hours for '{e.name}', using scheduling window")

            coords = None
            if e.coordinates and len(e.coordinates) >= 2:
                coords = (float(e.coordinates[0]), float(e.coordinates[1]))
            if coords is None:
                coords = geocode_address(e.address)

            errands.append(Errand(
                name=e.name,
                coordinates=coords,
                business_hours=hours,
                duration_minutes=e.duration_minutes,
                address=e.address,
            ))
        start_location = geocode_address(request.home_address)

        print(f"\nScheduling errands starting from location: {start_location}")
        print(f"Calendar timezone: {calendar_timezone}")

        scheduled = schedule_errands(
            errands=errands,
            events=events,
            start_location=start_location,
            start_date=start_date,
            end_date=end_date,
            calendar_timezone=calendar_timezone,
            buffer_minutes=request.buffer_minutes,
        )

        print_scheduled_errands(scheduled)

        scheduled_names = {s.errand.name for s in scheduled}
        unscheduled = [x for x in errands if x.name not in scheduled_names]
        if unscheduled:
            print(f"\n⚠ Could not schedule {len(unscheduled)} errand(s):")
            for errand in unscheduled:
                print(f"  - {errand.name}")

        # Prepare structured response for UI
        scheduled_payload = [
            {
                "name": s.errand.name,
                "address": s.errand.address,
                "start_time": s.start_time.isoformat(),
                "end_time": s.end_time.isoformat(),
                "travel_time_minutes": s.travel_time_minutes,
                "distance_km": s.distance_km,
            }
            for s in scheduled
        ]

        events_payload = []
        for ev in events:
            events_payload.append(
                {
                    "id": ev.get("id"),
                    "summary": ev.get("summary"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                }
            )

        return {
            "status": "ok",
            "window": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "calendar_timezone": calendar_timezone,
            },
            "scheduled_errands": scheduled_payload,
            "events": events_payload,
        }

    except HttpError as error:
        print(f"An error occurred: {error}")
        return {"status": "error", "detail": str(error)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
