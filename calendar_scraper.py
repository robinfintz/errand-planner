import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_credentials():
  """Gets valid user credentials from storage or runs OAuth flow.
  
  Returns:
      Credentials: The authorized credentials object.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      os.remove("token.json")
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())
  
  return creds


def get_calendar_timezone(service):
  """Gets the timezone of the primary calendar.
  
  Args:
      service: The Google Calendar API service object.
  
  Returns:
      str: The timezone string (e.g., 'America/New_York').
  """
  calendar = service.calendars().get(calendarId="primary").execute()
  return calendar.get("timeZone", "UTC")


def fetch_upcoming_events(service, max_results=10):
  """Fetches upcoming events from the user's calendar.
  
  Args:
      service: The Google Calendar API service object.
      max_results: Maximum number of events to fetch (default: 10).
  
  Returns:
      list: List of event dictionaries, or empty list if no events found.
  """
  now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
  print(f"Getting the upcoming {max_results} events")
  
  events_result = (
      service.events()
      .list(
          calendarId="primary",
          timeMin=now,
          maxResults=max_results,
          singleEvents=True,
          orderBy="startTime",
      )
      .execute()
  )
  return events_result.get("items", [])


def fetch_events_in_range(service, start_date, end_date):
  """Fetches all events within a date range from the user's calendar.
  
  Args:
      service: The Google Calendar API service object.
      start_date: Start datetime for the range.
      end_date: End datetime for the range.
  
  Returns:
      list: List of event dictionaries in the specified range.
  """
  # Convert to ISO format with timezone
  if start_date.tzinfo is None:
    start_date = start_date.replace(tzinfo=datetime.timezone.utc)
  if end_date.tzinfo is None:
    end_date = end_date.replace(tzinfo=datetime.timezone.utc)
  
  time_min = start_date.isoformat()
  time_max = end_date.isoformat()
  
  events = []
  page_token = None
  
  while True:
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=2500,  # Maximum allowed
            singleEvents=True,
            orderBy="startTime",
            pageToken=page_token,
        )
        .execute()
    )
    
    events.extend(events_result.get("items", []))
    page_token = events_result.get("nextPageToken")
    
    if not page_token:
      break
  
  return events


def convert_to_local_time(time_str):
  """Converts an ISO format time string to local time.
  
  Args:
      time_str: ISO format datetime string or date string.
  
  Returns:
      str: Formatted datetime string in local time, or original string if date-only.
  """
  try:
    # Try parsing as datetime with timezone
    dt = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    local_dt = dt.astimezone()
    return local_dt.strftime("%Y-%m-%d %I:%M:%S %p %Z")
  except (ValueError, AttributeError):
    # If it's a date-only string (YYYY-MM-DD), return as-is
    return time_str

