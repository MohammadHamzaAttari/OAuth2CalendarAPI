from django.urls import path
from .views import (
    GoogleCalendarInitView, GoogleCalendarRedirectView, GoogleCalendarEventsView,
    CheckAppointmentView, CreateAppointmentView
)

urlpatterns = [
    path('init/', GoogleCalendarInitView.as_view(), name='google_calendar_init'),
    path('redirect/', GoogleCalendarRedirectView.as_view(), name='google_calendar_redirect'),
    path('events/', GoogleCalendarEventsView.as_view(), name='google_calendar_events'),
    path('check_appointment', CheckAppointmentView.as_view(), name='check_appointment'),
    path('create_appointment', CreateAppointmentView.as_view(), name='create_appointment'),
]
