import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta
from weather.models import WeatherRecord, FavoriteCity


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='testpass123')


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username='otheruser', password='testpass123')


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def weather_record(db):
    return WeatherRecord.objects.create(
        city="Cairo, Egypt",
        temperature=30.0,
        humidity=40.0,
        wind_speed=10.0,
        recorded_at=timezone.now(),
        source='api',
    )


@pytest.fixture
def weather_record_older(db):
    return WeatherRecord.objects.create(
        city="Cairo, Egypt",
        temperature=25.0,
        humidity=45.0,
        wind_speed=8.0,
        recorded_at=timezone.now() - timedelta(hours=1),
        source='api',
    )