from django.urls import path

from .views import HealthView, TripPlanView

urlpatterns = [
    path("trip/plan/", TripPlanView.as_view(), name="trip-plan"),
    path("trip/health/", HealthView.as_view(), name="trip-health"),
]
