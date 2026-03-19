import datetime
import os
from typing import List, Optional, Tuple
from data_models.errand import Errand
import googlemaps

from data_models.scheduled_errand import ScheduledErrand

def _load_dotenv(path: str = ".env") -> None:
    """
    Minimal .env loader (no external dependency).
    Loads KEY=VALUE lines into os.environ if they are not already set.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


_load_dotenv()
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    raise RuntimeError(
        "Missing GOOGLE_MAPS_API_KEY. Set it in your .env file (or environment variables)."
    )

gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def geocode_address(address):
    """Convert address to coordinates using Google Maps Geocoding API.
    
    Args:
        address: String address (e.g., "1600 Amphitheatre Parkway, Mountain View, CA")
    
    Returns:
        Tuple of (latitude, longitude) or (None, None) if not found
    """
    try:
        result = gmaps.geocode(address)
        
        if result:
            location = result[0]['geometry']['location']
            lat = location['lat']
            lng = location['lng']
            return (lat, lng)
        else:
            print(f"Address not found: {address}")
            return (None, None)
            
    except Exception as e:
        print(f"Geocoding error: {e}")
        return (None, None)

def get_drive_time_and_distance(
    origin: Tuple[float, float],
    destination: Errand,
    departure_time: Optional[datetime.datetime] = None
) -> Tuple[float, float]:
    """Get driving time and distance between two coordinates using Google Maps API.
    
    Args:
        origin: (latitude, longitude) of starting point
        destination: (latitude, longitude) of ending point
        departure_time: Datetime for departure (for traffic-aware routing)
    
    Returns:
        Tuple of (travel_time_minutes, distance_km)
    """
    if destination.coordinates is None:
        try:
            destination.coordinates = geocode_address(destination.address)
        except Exception as e:
            print(f"Error geocoding address: {e}")
            return None, None
    try:
        result = gmaps.distance_matrix(
            origins=[origin],
            destinations=[destination.coordinates],
            mode="driving",
            departure_time=departure_time or datetime.datetime.now(),
            traffic_model="best_guess"
        )
        
        if result['rows'][0]['elements'][0]['status'] == 'OK':
            element = result['rows'][0]['elements'][0]
            
            # Get duration in traffic if available, otherwise regular duration
            duration_seconds = element.get('duration_in_traffic', {}).get('value') or element['duration']['value']
            distance_meters = element['distance']['value']
            
            travel_time_minutes = duration_seconds / 60
            distance_km = distance_meters / 1000
            
            return travel_time_minutes, distance_km
        else:
            # Fallback to estimation if API call fails
            print(f"Warning: Distance Matrix API returned {result['rows'][0]['elements'][0]['status']}, using fallback estimation")
            return estimate_travel_time_fallback(origin, destination.coordinates)
            
    except Exception as e:
        print(f"Error calling Distance Matrix API: {e}, using fallback estimation")
        return estimate_travel_time_fallback(origin, destination.coordinates)


def estimate_travel_time_fallback(
    origin: Tuple[float, float],
    destination: Tuple[float, float]
) -> Tuple[float, float]:
    """Fallback estimation using haversine formula if API fails.
    
    Args:
        origin: (latitude, longitude) of starting point
        destination: (latitude, longitude) of ending point
    
    Returns:
        Tuple of (travel_time_minutes, distance_km)
    """
    import math
    
    lat1, lon1 = origin
    lat2, lon2 = destination
    
    # Haversine formula
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    distance_km = c * 6371  # Earth radius in km
    
    # Estimate time assuming 50 km/h average speed
    travel_time_minutes = (distance_km / 50) * 60
    
    return travel_time_minutes, distance_km


def get_available_slots(
    events: List[dict],
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    calendar_timezone: str
) -> List[Tuple[datetime.datetime, datetime.datetime]]:
    """Extract available time slots from calendar events.
    
    Args:
        events: List of calendar event dictionaries
        start_date: Start of the period to check
        end_date: End of the period to check
        calendar_timezone: Timezone string
    
    Returns:
        List of (start, end) tuples representing available time slots
    """
    # Ensure start_date and end_date are timezone-aware
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=calendar_timezone)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=calendar_timezone)
    
    # Convert events to datetime objects
    busy_slots = []
    for event in events:
        start_str = event["start"].get("dateTime", event["start"].get("date"))
        end_str = event["end"].get("dateTime", event["end"].get("date"))
        
        try:
            # Parse ISO format datetime
            if "T" in start_str:
                start_dt = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_dt = datetime.datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                # Ensure timezone-aware
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=calendar_timezone)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=calendar_timezone)
                busy_slots.append((start_dt, end_dt))
            else:
                # Date-only event (all-day)
                start_dt = datetime.datetime.fromisoformat(start_str)
                end_dt = datetime.datetime.fromisoformat(end_str)
                tz = start_date.tzinfo or calendar_timezone
                start_dt = start_dt.replace(hour=0, minute=0, second=0, tzinfo=tz)
                end_dt = end_dt.replace(hour=23, minute=59, second=59, tzinfo=tz)
                busy_slots.append((start_dt, end_dt))
        except (ValueError, AttributeError) as e:
            continue
    
    # Sort busy slots by start time
    busy_slots.sort(key=lambda x: x[0])
    
    # Normalize all times to the same timezone
    target_tz = start_date.tzinfo or calendar_timezone
    
    start_date_normalized = start_date if start_date.tzinfo == target_tz else start_date.astimezone(target_tz)
    end_date_normalized = end_date if end_date.tzinfo == target_tz else end_date.astimezone(target_tz)
    
    # Convert all busy slots to target timezone
    normalized_busy_slots = []
    for busy_start, busy_end in busy_slots:
        if busy_start.tzinfo != target_tz:
            busy_start = busy_start.astimezone(target_tz)
        if busy_end.tzinfo != target_tz:
            busy_end = busy_end.astimezone(target_tz)
        normalized_busy_slots.append((busy_start, busy_end))
    
    # Merge overlapping busy periods
    merged_busy_slots = []
    for busy_start, busy_end in normalized_busy_slots:
        if busy_end < start_date_normalized:
            continue
        if busy_start > end_date_normalized:
            break
        
        busy_start = max(busy_start, start_date_normalized)
        busy_end = min(busy_end, end_date_normalized)
        
        if not merged_busy_slots:
            merged_busy_slots.append((busy_start, busy_end))
        else:
            last_start, last_end = merged_busy_slots[-1]
            if busy_start <= last_end:
                merged_busy_slots[-1] = (last_start, max(last_end, busy_end))
            else:
                merged_busy_slots.append((busy_start, busy_end))
    
    # Find available slots
    available_slots = []
    current_time = start_date_normalized
    
    for busy_start, busy_end in merged_busy_slots:
        if busy_start.tzinfo != target_tz:
            busy_start = busy_start.astimezone(target_tz)
        if busy_end.tzinfo != target_tz:
            busy_end = busy_end.astimezone(target_tz)
        
        if current_time < busy_start:
            available_slots.append((current_time, busy_start))
        
        current_time = max(current_time, busy_end)
    
    if current_time < end_date_normalized:
        available_slots.append((current_time, end_date_normalized))
    
    # Normalize all slots
    normalized_slots = []
    for slot_start, slot_end in available_slots:
        if slot_start.tzinfo != target_tz:
            slot_start = slot_start.astimezone(target_tz)
        if slot_end.tzinfo != target_tz:
            slot_end = slot_end.astimezone(target_tz)
        normalized_slots.append((slot_start, slot_end))
    
    return normalized_slots


def find_nearest_errand(
    current_location: Tuple[float, float],
    remaining_errands: List[Errand],
    current_time: datetime.datetime
) -> Tuple[Optional[Errand], float, float]:
    """Find the nearest errand that's open at the current time using Distance Matrix API.
    
    Args:
        current_location: (latitude, longitude) of current position
        remaining_errands: List of errands not yet scheduled
        current_time: Current datetime
    
    Returns:
        Tuple of (nearest_open_errand, travel_time_minutes, distance_km) or (None, inf, inf) if none open
    """
    nearest_errand = None
    min_travel_time = float('inf')
    min_distance = float('inf')
    
    for errand in remaining_errands:
        # Check if errand is open
        if not errand.is_open_at(current_time):
            continue
        
        # Get actual drive time and distance from Google Maps
        travel_time, distance = get_drive_time_and_distance(
            current_location,
            errand,
            current_time
        )
        
        # Use travel time as primary metric (accounts for traffic)
        if travel_time < min_travel_time:
            min_travel_time = travel_time
            min_distance = distance
            nearest_errand = errand
    
    return nearest_errand, min_travel_time, min_distance

def schedule_errands(
    errands: List[Errand],
    events: List[dict],
    start_location: Tuple[float, float],
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    calendar_timezone: str,
    buffer_minutes: int = 15
) -> List[ScheduledErrand]:
    """Schedule errands optimally based on calendar availability, distance, and business hours.
    
    Args:
        errands: List of errands to schedule
        events: List of calendar events
        start_location: Starting location (latitude, longitude)
        start_date: When to start scheduling
        end_date: When to stop scheduling
        calendar_timezone: Timezone string
        buffer_minutes: Buffer time between errands in minutes
    
    Returns:
        List of scheduled errands in optimal order
    """
    debug_enabled = os.environ.get("ERRAND_SCHED_DEBUG", "0") == "1"
    target_errand_name = os.environ.get("ERRAND_SCHED_TARGET", "").strip()

    available_slots = get_available_slots(events, start_date, end_date, calendar_timezone)
    
    if not available_slots:
        return []
    
    scheduled = []
    remaining_errands = errands.copy()
    current_location = start_location
    
    for slot_idx, (slot_start, slot_end) in enumerate(available_slots, 1):
        if slot_start.tzinfo is None:
            slot_start = slot_start.replace(tzinfo=datetime.timezone.utc)
        if slot_end.tzinfo is None:
            slot_end = slot_end.replace(tzinfo=datetime.timezone.utc)
        
        print(f"\nProcessing Slot {slot_idx}: [{slot_start} to {slot_end}] (duration: {(slot_end-slot_start).total_seconds()/60:.1f} min)")
        current_time = slot_start
        # If an errand can't fit in this specific calendar slot (e.g. it closes before completion),
        # we should not permanently remove it; it might fit in a later slot/day.
        blocked_errand_ids: set[int] = set()
        
        if slot_end <= slot_start:
            print(f"  Skipping invalid slot (end <= start)")
            continue
        
        while current_time < slot_end and remaining_errands:
            # Optional targeted debug: explain why a specific errand can't fit
            if debug_enabled and target_errand_name:
                target_errand = next(
                    (er for er in remaining_errands if er.name == target_errand_name),
                    None,
                )
                if target_errand is not None:
                    try:
                        travel_time, distance = get_drive_time_and_distance(
                            current_location, target_errand, current_time
                        )
                        arrival_time = None
                        errand_end_time = None
                        if travel_time is not None:
                            arrival_time = current_time + datetime.timedelta(
                                minutes=travel_time
                            )
                            errand_end_time = arrival_time + datetime.timedelta(
                                minutes=target_errand.duration_minutes
                            )

                        open_at_arrival = (
                            target_errand.is_open_at(arrival_time)
                            if arrival_time is not None
                            else False
                        )
                        end_check = (
                            errand_end_time - datetime.timedelta(seconds=1)
                            if errand_end_time is not None
                            else None
                        )
                        open_at_end = (
                            target_errand.is_open_at(end_check)
                            if end_check is not None
                            else False
                        )

                        fits_slot_end = (
                            errand_end_time is not None and errand_end_time <= slot_end
                        )
                        fits_arrival_window = (
                            arrival_time is not None
                            and arrival_time >= slot_start
                            and arrival_time < slot_end
                        )

                        # Compute a concise failure reason
                        failure_reasons = []
                        if arrival_time is None:
                            failure_reasons.append("no_travel_time")
                        else:
                            if not fits_arrival_window:
                                failure_reasons.append("arrival_outside_slot")
                            if not open_at_arrival:
                                failure_reasons.append("not_open_at_arrival")
                            if not fits_slot_end:
                                failure_reasons.append("end_exceeds_slot_end")
                            if not open_at_end:
                                failure_reasons.append("not_open_at_end")

                        print(
                            f"DEBUG TARGET '{target_errand_name}': slot=[{slot_start}..{slot_end}] "
                            f"current_time={current_time}, current_loc={current_location} "
                            f"travel={travel_time}min distance={distance}km arrival={arrival_time} end={errand_end_time} "
                            f"open_at_arrival={open_at_arrival} open_at_end={open_at_end} "
                            f"fits_arrival={fits_arrival_window} fits_end={fits_slot_end} "
                            f"reasons={failure_reasons}"
                        )
                    except Exception as e:
                        print(f"DEBUG TARGET scheduling check failed: {e}")
            # Find nearest errand using Distance Matrix API.
            # Skip errands that already failed within this slot.
            candidate_errands = [
                e for e in remaining_errands if id(e) not in blocked_errand_ids
            ]
            nearest_errand, travel_time, distance = find_nearest_errand(
                current_location, candidate_errands, current_time
            )
            
            if nearest_errand is None:
                break
            
            # Calculate when we'd arrive
            arrival_time = current_time + datetime.timedelta(minutes=travel_time)
            
            if arrival_time.tzinfo is None:
                arrival_time = arrival_time.replace(tzinfo=slot_start.tzinfo or datetime.timezone.utc)
            
            if arrival_time >= slot_end:
                break
            
            # Must start during business hours
            if not nearest_errand.is_open_at(arrival_time):
                blocked_errand_ids.add(id(nearest_errand))
                continue
            
            errand_end_time = arrival_time + datetime.timedelta(minutes=nearest_errand.duration_minutes)
            
            if errand_end_time.tzinfo is None:
                errand_end_time = errand_end_time.replace(tzinfo=slot_start.tzinfo or datetime.timezone.utc)

            # Must finish before the slot ends
            if errand_end_time > slot_end:
                blocked_errand_ids.add(id(nearest_errand))
                continue

            # Must also finish during business hours (not just at arrival)
            # Use a 1-second epsilon so errands that end exactly at closing time are allowed.
            end_check = errand_end_time - datetime.timedelta(seconds=1)
            if not nearest_errand.is_open_at(end_check):
                blocked_errand_ids.add(id(nearest_errand))
                continue
            
            if arrival_time < slot_start or arrival_time >= slot_end:
                print(f"ERROR: arrival_time {arrival_time} outside slot [{slot_start}, {slot_end})")
                break
            
            print(f"SCHEDULING: {nearest_errand.name} in slot [{slot_start}, {slot_end}): arrival={arrival_time}, end={errand_end_time}, travel={travel_time:.1f}min, distance={distance:.2f}km")
            scheduled.append(ScheduledErrand(
                errand=nearest_errand,
                start_time=arrival_time,
                end_time=errand_end_time,
                travel_time_minutes=travel_time,
                distance_km=distance
            ))
            
            current_location = nearest_errand.coordinates
            current_time = errand_end_time + datetime.timedelta(minutes=buffer_minutes)
            remaining_errands.remove(nearest_errand)
    
    # Final validation
    validated_scheduled = []
    busy_slots = []
    for event in events:
        start_str = event["start"].get("dateTime", event["start"].get("date"))
        end_str = event["end"].get("dateTime", event["end"].get("date"))
        try:
            if "T" in start_str:
                start_dt = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_dt = datetime.datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
                busy_slots.append((start_dt, end_dt))
            else:
                start_dt = datetime.datetime.fromisoformat(start_str)
                end_dt = datetime.datetime.fromisoformat(end_str)
                tz = start_date.tzinfo or datetime.timezone.utc
                start_dt = start_dt.replace(hour=0, minute=0, second=0, tzinfo=tz)
                end_dt = end_dt.replace(hour=23, minute=59, second=59, tzinfo=tz)
                busy_slots.append((start_dt, end_dt))
        except (ValueError, AttributeError):
            continue
    
    for scheduled_errand in scheduled:
        conflicts = False
        for busy_start, busy_end in busy_slots:
            if (scheduled_errand.start_time < busy_end and scheduled_errand.end_time > busy_start):
                conflicts = True
                print(f"CONFLICT DETECTED: {scheduled_errand.errand.name} scheduled {scheduled_errand.start_time} to {scheduled_errand.end_time} conflicts with event {busy_start} to {busy_end}")
                break
        if not conflicts:
            validated_scheduled.append(scheduled_errand)
        else:
            print(f"Warning: Removed {scheduled_errand.errand.name} due to calendar conflict")
    
    return validated_scheduled


def print_scheduled_errands(scheduled: List[ScheduledErrand]):
    """Print the scheduled errands in a formatted way.
    
    Args:
        scheduled: List of scheduled errands
    """
    if not scheduled:
        print("No errands could be scheduled.")
        return
    
    print("\n" + "="*70)
    print("SCHEDULED ERRANDS")
    print("="*70)
    
    total_distance = 0
    for i, scheduled_errand in enumerate(scheduled, 1):
        errand = scheduled_errand.errand
        start_str = scheduled_errand.start_time.strftime("%Y-%m-%d %I:%M %p")
        end_str = scheduled_errand.end_time.strftime("%I:%M %p")
        travel_str = f"{scheduled_errand.travel_time_minutes:.1f} min" if scheduled_errand.travel_time_minutes > 0 else "0 min"
        distance_str = f"{scheduled_errand.distance_km:.2f} km" if scheduled_errand.distance_km > 0 else "0 km"
        
        print(f"\n{i}. {errand.name}")
        if errand.address:
            print(f"   Location: {errand.address}")
        print(f"   Coordinates: ({errand.coordinates[0]:.6f}, {errand.coordinates[1]:.6f})")
        print(f"   Time: {start_str} to {end_str}")
        print(f"   Travel: {travel_str} ({distance_str})")
        print(f"   Duration: {errand.duration_minutes} minutes")
        
        total_distance += scheduled_errand.distance_km
    
    total_time = sum(
        s.errand.duration_minutes + s.travel_time_minutes 
        for s in scheduled
    )
    print(f"\n{'='*70}")
    print(f"Total time: {total_time:.1f} minutes ({total_time/60:.1f} hours)")
    print(f"Total distance: {total_distance:.2f} km ({total_distance*0.621371:.2f} miles)")
    print(f"Total errands scheduled: {len(scheduled)}")
    print("="*70)
