import pytest
from unittest.mock import patch, MagicMock
from django.test import override_settings
from weather.tasks import fetch_weather_data
from weather.models import WeatherRecord

pytestmark = pytest.mark.django_db

FAKE_CITIES = {
    "Cairo, Egypt": {"latitude": 30.0444, "longitude": 31.2357},
    "Alexandria, Egypt": {"latitude": 31.2001, "longitude": 29.9187},
}


def make_open_meteo_response(temperature=30.0, humidity=40.0, wind_speed=10.0):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "current": {
            "time": "2026-08-19T12:00",
            "temperature_2m": temperature,
            "relative_humidity_2m": humidity,
            "wind_speed_10m": wind_speed,
        }
    }
    return mock_response


class TestFetchWeatherData:
    @override_settings(WEATHER_CITIES=FAKE_CITIES)
    @patch('weather.tasks.requests.get')
    def test_creates_one_record_per_city(self, mock_get):
        mock_get.return_value = make_open_meteo_response()

        fetch_weather_data()

        assert WeatherRecord.objects.count() == 2
        assert mock_get.call_count == 2

    @override_settings(WEATHER_CITIES=FAKE_CITIES)
    @patch('weather.tasks.requests.get')
    def test_record_fields_match_api_response(self, mock_get):
        mock_get.return_value = make_open_meteo_response(
            temperature=35.5, humidity=22.0, wind_speed=14.0
        )

        fetch_weather_data()

        record = WeatherRecord.objects.first()
        assert record.temperature == 35.5
        assert record.humidity == 22.0
        assert record.wind_speed == 14.0
        assert record.source == 'api'

    @override_settings(WEATHER_CITIES=FAKE_CITIES)
    @patch('weather.tasks.requests.get')
    def test_recorded_at_is_timezone_aware(self, mock_get):
        mock_get.return_value = make_open_meteo_response()

        fetch_weather_data()

        record = WeatherRecord.objects.first()
        assert record.recorded_at.tzinfo is not None

    @override_settings(WEATHER_CITIES=FAKE_CITIES)
    @patch('weather.tasks.requests.get')
    def test_one_city_failing_does_not_stop_the_others(self, mock_get):
        """One city's request fails; the other city should still get a record."""
        import requests

        def side_effect(*args, **kwargs):
            if kwargs['params']['latitude'] == FAKE_CITIES["Cairo, Egypt"]["latitude"]:
                raise requests.exceptions.ConnectionError("network down")
            return make_open_meteo_response()

        mock_get.side_effect = side_effect

        fetch_weather_data()

        # only Alexandria should have succeeded
        assert WeatherRecord.objects.count() == 1
        assert WeatherRecord.objects.first().city == "Alexandria, Egypt"

    @override_settings(WEATHER_CITIES=FAKE_CITIES)
    @patch('weather.tasks.requests.get')
    def test_all_cities_failing_creates_no_records(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("network down")

        fetch_weather_data()

        assert WeatherRecord.objects.count() == 0