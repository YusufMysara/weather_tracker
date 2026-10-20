import pytest
from django.contrib.auth.models import User

pytestmark = pytest.mark.django_db


class TestLatest:
    def test_latest_is_public_and_returns_newest_per_city(self, api_client, weather_record, weather_record_older):
        response = api_client.get('/api/weather/latest/')
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['temperature'] == 30.0

    def test_latest_empty(self, api_client):
        response = api_client.get('/api/weather/latest/')
        assert response.status_code == 200
        assert response.data == []


class TestCities:
    def test_city_list_is_public(self, api_client):
        response = api_client.get('/api/cities/')
        assert response.status_code == 200
        assert 'Cairo, Egypt' in response.data
        assert len(response.data) == 27


class TestDemoLogin:
    def test_demo_login_returns_usable_tokens(self, api_client):
        response = api_client.post('/api/demo-login/')
        assert response.status_code == 200
        assert {'access', 'refresh'} <= response.data.keys()

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        assert api_client.get('/api/favorite-cities/').status_code == 200

    def test_demo_user_cannot_password_login(self, api_client):
        api_client.post('/api/demo-login/')
        assert not User.objects.get(username='demo').has_usable_password()

    def test_demo_login_is_idempotent(self, api_client):
        api_client.post('/api/demo-login/')
        api_client.post('/api/demo-login/')
        assert User.objects.filter(username='demo').count() == 1
