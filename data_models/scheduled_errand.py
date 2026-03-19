import datetime
from dataclasses import dataclass
from data_models.errand import Errand

@dataclass
class ScheduledErrand:
    """Represents an errand with scheduled start and end times."""
    errand: Errand
    start_time: datetime.datetime
    end_time: datetime.datetime
    travel_time_minutes: float = 0  # Travel time to get to this errand
    distance_km: float = 0  # Distance traveled to reach this errand