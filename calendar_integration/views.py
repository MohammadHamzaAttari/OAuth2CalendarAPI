from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
import requests
import json
import os
from google.auth.transport.requests import Request
import datetime
import logging

logger = logging.getLogger(__name__)

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

class GoogleCalendarInitView(View):
    def get(self, request):
        flow = Flow.from_client_secrets_file(
            settings.CLIENT_SECRETS_FILE,
            scopes=settings.SCOPES,
            redirect_uri=settings.REDIRECT_URI
        )
        auth_url, _ = flow.authorization_url(prompt='consent')
        return redirect(auth_url)

class GoogleCalendarRedirectView(View):
    def get(self, request):
        flow = Flow.from_client_secrets_file(
            settings.CLIENT_SECRETS_FILE,
            scopes=settings.SCOPES,
            redirect_uri=settings.REDIRECT_URI
        )
        flow.fetch_token(code=request.GET.get('code'))
        credentials = flow.credentials

        with open(settings.TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())

        return redirect('/events')

def refresh_access_token_if_needed():
    if not os.path.exists(settings.TOKEN_FILE):
        return None

    with open(settings.TOKEN_FILE, 'r') as token:
        credentials_data = json.load(token)
    print("refresh code executed",credentials_data['token'])
    credentials = Credentials.from_authorized_user_info(credentials_data, settings.SCOPES)
    print(credentials.expired)
    print(credentials.refresh_token)
    if credentials.expired and credentials.refresh_token:
        
        credentials.refresh(Request())

        with open(settings.TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())
        
    return credentials

class GoogleCalendarEventsView(View):
    def get(self, request):
        credentials = refresh_access_token_if_needed()
        if not credentials:
            return redirect('/authorize')

        service = build('calendar', 'v3', credentials=credentials)

        now = datetime.datetime.aware().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(
            calendarId='ceb9ac865e05baa14bf6515afa25761dbb82f6394ddf86aec98c464822db67b2@group.calendar.google.com',
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        return JsonResponse(events, safe=False)

def check_appointment(date_time):
    credentials = refresh_access_token_if_needed()
    if not credentials:
        raise Exception('No tokens found')

    service = build('calendar', 'v3', credentials=credentials)

    try:
        # Preprocess datetime string to ensure ISO 8601 compliance
        if ' ' in date_time:
            date_time = date_time.replace(' ', '+')
        start = datetime.datetime.fromisoformat(date_time)
    except ValueError:
        raise Exception(f'Invalid datetime format: {date_time}')
   
    end = start + datetime.timedelta(minutes=30)

    # Convert datetime objects to ISO format strings
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    events_result = service.events().list(
        calendarId='ceb9ac865e05baa14bf6515afa25761dbb82f6394ddf86aec98c464822db67b2@group.calendar.google.com',
        timeMin=start_iso,
        timeMax=end_iso,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    # Check if there are any events within the specified time range
    return len(events) > 0
# View to handle checking appointment
class CheckAppointmentView(View):
    def get(self, request):
        date_time = request.GET.get('date_time')
        
        if not date_time:
            return JsonResponse({'error': 'date_time query parameter is required'}, status=400)

        try:
            is_booked = check_appointment(date_time)
            return JsonResponse({'status': 'True' if is_booked else 'False'})
        except Exception as e:
            return JsonResponse({'error': f'Error checking appointment: {str(e)}'}, status=500)
@method_decorator(csrf_exempt, name='dispatch')
class CreateAppointmentView(View):
    def post(self, request):
        try:
            logger.info(f"Request body: {request.body}")
            data = json.loads(request.body)
            print(data)
        except json.JSONDecodeError as e:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        date_time = data.get('Date_time')
        name = data.get('Name')
        email = data.get('Email')
        contact_number = data.get('Contact_Number')

        if not all([date_time, name, email, contact_number]):
            return JsonResponse({'error': 'All fields are required'}, status=400)

        try:
            is_booked = check_appointment(date_time)
            if is_booked:
                return JsonResponse({'message': 'Sorry, date already booked. Choose another one.'}, status=400)

            credentials = refresh_access_token_if_needed()
            if not credentials:
                return redirect('/authorize')

            service = build('calendar', 'v3', credentials=credentials)

            event = {
                'summary': name,
                'description': f'Contact Number: {contact_number}',
                'start': {
                    'dateTime': date_time,
                    'timeZone': 'America/Los_Angeles',
                },
                'end': {
                    'dateTime': (datetime.datetime.fromisoformat(date_time) + datetime.timedelta(minutes=30)).isoformat(),
                    'timeZone': 'America/Los_Angeles',
                },
                'attendees': [{'email': email}],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 10},
                    ],
                },
            }

            event_result = service.events().insert(calendarId='ceb9ac865e05baa14bf6515afa25761dbb82f6394ddf86aec98c464822db67b2@group.calendar.google.com', body=event).execute()

            return JsonResponse({
                'Status': 'SUCCESS',
                'Date': date_time.split('T')[0],
                'Name': name,
                'Email': email,
                'Contact_Number': contact_number,
            })
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            return JsonResponse({'error': f'Error creating event: {str(e)}'}, status=500)