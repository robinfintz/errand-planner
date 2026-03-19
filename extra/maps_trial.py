import googlemaps
from datetime import datetime
import os

# Initialize the client (key must come from env/.env)
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise RuntimeError("Missing GOOGLE_MAPS_API_KEY. Set it in your .env or environment variables.")

gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def get_drive_time(origin, destination, departure_time=None):
    """Calculate driving time between two locations.
    
    Args:
        origin: Starting address or (lat, lng) tuple
        destination: Ending address or (lat, lng) tuple
        departure_time: datetime object for departure (optional, for traffic)
    
    Returns:
        dict: Contains duration in seconds, duration in traffic, and distance
    """
    try:
        # Use Distance Matrix API for drive time
        result = gmaps.distance_matrix(
            origins=origin,
            destinations=destination,
            mode="driving",
            departure_time=departure_time or datetime.now(),
            traffic_model="best_guess"  # or "pessimistic", "optimistic"
        )
        
        if result['rows'][0]['elements'][0]['status'] == 'OK':
            element = result['rows'][0]['elements'][0]
            
            # Extract data
            distance = element['distance']['value']  # meters
            duration = element['duration']['value']  # seconds
            
            # Duration in traffic (if available)
            duration_in_traffic = element.get('duration_in_traffic', {}).get('value', duration)
            
            return {
                'distance_meters': distance,
                'distance_km': distance / 1000,
                'distance_miles': distance / 1609.34,
                'duration_seconds': duration,
                'duration_minutes': duration / 60,
                'duration_in_traffic_seconds': duration_in_traffic,
                'duration_in_traffic_minutes': duration_in_traffic / 60,
                'origin': origin,
                'destination': destination
            }
        else:
            print(f"Error: {result['rows'][0]['elements'][0]['status']}")
            return None
            
    except Exception as e:
        print(f"Error calculating drive time: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # Using addresses
    origin = "1600 Amphitheatre Parkway, Mountain View, CA"
    destination = "1 Apple Park Way, Cupertino, CA"
    
    result = get_drive_time(origin, destination)
    
    if result:
        print(f"Distance: {result['distance_km']:.2f} km ({result['distance_miles']:.2f} miles)")
        print(f"Duration: {result['duration_minutes']:.2f} minutes")
        print(f"Duration in traffic: {result['duration_in_traffic_minutes']:.2f} minutes")
    
    # Using coordinates
    origin_coords = (37.4224764, -122.0842499)  # Google HQ
    dest_coords = (37.3318456, -122.0296002)    # Apple Park
    
    result2 = get_drive_time(origin_coords, dest_coords)
    if result2:
        print(f"\nWith coordinates:")
        print(f"Duration: {result2['duration_minutes']:.2f} minutes")