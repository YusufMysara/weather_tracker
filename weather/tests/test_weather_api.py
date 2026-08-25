import pytest

pytestmark = pytest.mark.django_db


class TestWeatherReadAccess:
    def test_list_is_public(self, api_client, weather_record):
        response = api_client.get('/api/weather/')
        assert response.status_code == 200

    def test_retrieve_is_public(self, api_client, weather_record):
        response = api_client.get(f'/api/weather/{weather_record.id}/')
        assert response.status_code == 200

    def test_list_filters_by_city(self, api_client, weather_record):
        response = api_client.get('/api/weather/?city=Cairo, Egypt')
        assert response.status_code == 200
        assert all(r['city'] == 'Cairo, Egypt' for r in response.data)

    def test_list_unknown_city_returns_empty(self, api_client, weather_record):
        response = api_client.get('/api/weather/?city=NotARealCity')
        assert response.status_code == 200
        assert response.data == []


class TestWeatherWriteAccess:
    def test_update_requires_auth(self, api_client, weather_record):
        response = api_client.patch(f'/api/weather/{weather_record.id}/', {'humidity': 55.0})
        assert response.status_code == 401

    def test_update_succeeds_when_authenticated(self, auth_client, weather_record):
        response = auth_client.patch(f'/api/weather/{weather_record.id}/', {'humidity': 55.0})
        assert response.status_code == 200
        assert response.data['humidity'] == 55.0

    def test_delete_requires_auth(self, api_client, weather_record):
        response = api_client.delete(f'/api/weather/{weather_record.id}/')
        assert response.status_code == 401

    def test_delete_succeeds_when_authenticated(self, auth_client, weather_record):
        response = auth_client.delete(f'/api/weather/{weather_record.id}/')
        assert response.status_code == 204

    def test_create_does_not_exist(self, auth_client):
        response = auth_client.post('/api/weather/', {
            'city': 'Test City', 'temperature': 20.0,
            'humidity': 50.0, 'wind_speed': 5.0, 'recorded_at': '2026-01-01T00:00:00Z',
        })
        assert response.status_code == 405


class TestTemperatureDiff:
    def test_null_when_no_previous_record(self, api_client, weather_record):
        response = api_client.get(f'/api/weather/{weather_record.id}/')
        assert response.data['temperature_diff'] is None

    def test_computed_against_previous_record(self, api_client, weather_record, weather_record_older):
        response = api_client.get(f'/api/weather/{weather_record.id}/')
        # weather_record (30.0) vs weather_record_older (25.0) -> diff = 5.0
        assert response.data['temperature_diff'] == 5.0


class TestExportThrottle:
    def test_export_requires_auth(self, api_client, weather_record):
        response = api_client.get('/api/weather/export/')
        assert response.status_code == 401

    def test_export_succeeds_when_authenticated(self, auth_client, weather_record):
        response = auth_client.get('/api/weather/export/')
        assert response.status_code == 200
        assert response['Content-Type'] == (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )