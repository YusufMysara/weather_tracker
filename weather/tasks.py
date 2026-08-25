from django.core.mail import send_mail
import requests
from celery import shared_task
from django.conf import settings
from .models import WeatherRecord
from datetime import datetime
from django.utils import timezone as django_timezone


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def fetch_weather_data(self) -> None:
    url = "https://api.open-meteo.com/v1/forecast"

    for city_name, coords in settings.WEATHER_CITIES.items():
        params = {
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            current = data["current"]

            WeatherRecord.objects.create(
                city=city_name,
                temperature=current["temperature_2m"],
                humidity=current["relative_humidity_2m"],
                wind_speed=current["wind_speed_10m"],
                recorded_at=django_timezone.make_aware(datetime.fromisoformat(current["time"])),
                source="api",
            )
            if current["temperature_2m"] > 35:
                send_mail(
                    subject=f"Heat Alert: {city_name}",
                    message=f"Temperature in {city_name} has reached {current['temperature_2m']}°C.",
                    from_email=None,
                    recipient_list=["your_real_email@example.com"],
                )
        except requests.RequestException:
            continue