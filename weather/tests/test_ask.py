import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.django_db


def make_gemini_mock(json_text):
    mock_response = MagicMock()
    mock_response.text = json_text
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    return mock_model


class TestAskValidation:
    def test_requires_auth(self, api_client):
        response = api_client.post('/api/weather/ask/', {'question': 'hottest city?'}, format='json')
        assert response.status_code == 401

    def test_requires_question_field(self, auth_client):
        response = auth_client.post('/api/weather/ask/', {}, format='json')
        assert response.status_code == 400

    @patch('weather.views.genai.GenerativeModel')
    def test_unsupported_question_returns_422(self, mock_model_class, auth_client):
        mock_model_class.return_value = make_gemini_mock('{"unsupported": true}')
        response = auth_client.post(
            '/api/weather/ask/', {'question': 'Will it rain tomorrow?'}, format='json'
        )
        assert response.status_code == 422

    @patch('weather.views.genai.GenerativeModel')
    def test_invalid_metric_returns_422(self, mock_model_class, auth_client):
        mock_model_class.return_value = make_gemini_mock(
            '{"scope": "single_city", "city": "Cairo, Egypt", '
            '"metric": "pressure", "aggregation": "latest"}'
        )
        response = auth_client.post(
            '/api/weather/ask/', {'question': 'pressure in Cairo?'}, format='json'
        )
        assert response.status_code == 422

    @patch('weather.views.genai.GenerativeModel')
    def test_latest_aggregation_does_not_crash(self, mock_model_class, auth_client, weather_record):
        """Regression test for the UnboundLocalError bug — the 'latest' branch
        must reach the answer-phrasing step without crashing."""
        mock_gemini = MagicMock()
        mock_gemini.generate_content.side_effect = [
            MagicMock(text=(
                '{"scope": "single_city", "city": "Cairo, Egypt", '
                '"metric": "temperature", "aggregation": "latest"}'
            )),
            MagicMock(text='{"answer": "It is 30.0 degrees in Cairo right now."}'),
        ]
        mock_model_class.return_value = mock_gemini

        response = auth_client.post(
            '/api/weather/ask/', {'question': 'temperature in Cairo now?'}, format='json'
        )
        assert response.status_code == 200
        assert response.data['raw_result']['value'] == 30.0