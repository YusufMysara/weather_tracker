import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.django_db


def make_gemini_mock(json_text):
    mock_response = MagicMock()
    mock_response.text = json_text
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    return mock_model


class TestInsights:
    def test_requires_auth(self, api_client, weather_record):
        response = api_client.get('/api/weather/insights/?city=Cairo, Egypt')
        assert response.status_code == 401

    def test_requires_city_param(self, auth_client):
        response = auth_client.get('/api/weather/insights/')
        assert response.status_code == 400

    def test_unknown_city_returns_404(self, auth_client):
        response = auth_client.get('/api/weather/insights/?city=Nowhere')
        assert response.status_code == 404

    @patch('weather.views.genai.GenerativeModel')
    def test_returns_parsed_ai_fields(self, mock_model_class, auth_client, weather_record):
        mock_model_class.return_value = make_gemini_mock(
            '{"summary": "Mild and stable.", '
            '"activities": ["walking", "cycling", "picnic"], '
            '"warnings": ["No significant weather risks at this time."], '
            '"anomaly": "Consistent with the recent average, nothing unusual."}'
        )

        response = auth_client.get('/api/weather/insights/?city=Cairo, Egypt')

        assert response.status_code == 200
        assert response.data['summary'] == "Mild and stable."
        assert len(response.data['activities']) == 3
        assert response.data['warnings'] != []
        assert response.data['anomaly'] is not None

    @patch('weather.views.genai.GenerativeModel')
    def test_malformed_ai_response_returns_502(self, mock_model_class, auth_client, weather_record):
        mock_model_class.return_value = make_gemini_mock('not valid json at all')

        response = auth_client.get('/api/weather/insights/?city=Cairo, Egypt')

        assert response.status_code == 502

    @patch('weather.views.genai.GenerativeModel')
    def test_empty_ai_response_returns_502(self, mock_model_class, auth_client, weather_record):
        mock_model_class.return_value = make_gemini_mock('')

        response = auth_client.get('/api/weather/insights/?city=Cairo, Egypt')

        assert response.status_code == 502


class TestForecast:
    def test_requires_auth(self, api_client):
        response = api_client.get('/api/weather/forecast/?city=Cairo, Egypt')
        assert response.status_code == 401

    def test_requires_city_param(self, auth_client):
        response = auth_client.get('/api/weather/forecast/')
        assert response.status_code == 400

    def test_unknown_city_returns_404(self, auth_client):
        response = auth_client.get('/api/weather/forecast/?city=Nowhere')
        assert response.status_code == 404

    @patch('weather.views.genai.GenerativeModel')
    @patch('weather.views.requests.get')
    def test_returns_forecast_and_narration(self, mock_get, mock_model_class, auth_client):
        mock_open_meteo = MagicMock()
        mock_open_meteo.raise_for_status.return_value = None
        mock_open_meteo.json.return_value = {
            "daily": {
                "time": ["2026-08-20", "2026-08-21", "2026-08-22"],
                "temperature_2m_max": [37.0, 35.0, 34.0],
                "temperature_2m_min": [24.0, 23.0, 22.0],
                "precipitation_sum": [0, 0, 0],
            }
        }
        mock_get.return_value = mock_open_meteo
        mock_model_class.return_value = make_gemini_mock(
            '{"forecast_summary": "Hot and dry, cooling slightly over three days.", '
            '"recommendation": "Stay hydrated."}'
        )

        response = auth_client.get('/api/weather/forecast/?city=Cairo, Egypt')

        assert response.status_code == 200
        assert len(response.data['raw_forecast']) == 3
        assert response.data['raw_forecast'][0]['high'] == 37.0
        assert response.data['forecast_summary'] is not None

    @patch('weather.views.requests.get')
    def test_open_meteo_failure_returns_502(self, mock_get, auth_client):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("network down")

        response = auth_client.get('/api/weather/forecast/?city=Cairo, Egypt')

        assert response.status_code == 502