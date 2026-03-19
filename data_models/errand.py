import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Errand:
    """Represents an errand with location and business hours."""
    name: str
    business_hours: dict  # e.g., {"monday": "9:00-17:00", "tuesday": "9:00-17:00", ...}
    duration_minutes: int  # Estimated time needed to complete the errand
    coordinates: Optional[Tuple[float, float]] = None  # (latitude, longitude) - optional
    address: Optional[str] = None  # Address required if coordinates are not provided
    
    def is_open_at(self, dt: datetime.datetime) -> bool:
        """Check if errand location is open at the given datetime."""
        day_name = dt.strftime("%A").lower()
        if day_name not in self.business_hours:
            return False
        
        hours = self.business_hours[day_name]
        if hours == "closed" or not hours:
            return False
        
        try:
            open_time, close_time = hours.split("-")
            open_hour, open_min = map(int, open_time.split(":"))
            close_hour, close_min = map(int, close_time.split(":"))
            
            current_time = dt.time()
            open_dt = datetime.time(open_hour, open_min)
            close_dt = datetime.time(close_hour, close_min)

            # Normal same-day window, e.g. 09:00–21:00
            if open_dt <= close_dt:
                return open_dt <= current_time <= close_dt

            # Overnight window, e.g. 09:00–02:00 next day:
            # treat as open from open_dt to midnight, and from midnight to close_dt
            return current_time >= open_dt or current_time <= close_dt
        except (ValueError, AttributeError):
            return False