import pytest

pytestmark = pytest.mark.django_db


class TestFavoriteCity:
    def test_requires_auth(self, api_client):
        response = api_client.get('/api/favorite-cities/')
        assert response.status_code == 401

    def test_create_favorite(self, auth_client):
        response = auth_client.post('/api/favorite-cities/', {'city': 'Cairo, Egypt'})
        assert response.status_code == 201
        assert response.data['city'] == 'Cairo, Egypt'

    def test_user_is_auto_assigned_not_client_supplied(self, auth_client, user, other_user):
        response = auth_client.post('/api/favorite-cities/', {
            'city': 'Cairo, Egypt',
            'user': other_user.id,  # attempt to spoof owner — must be ignored
        })
        assert response.status_code == 201
        assert response.data['user'] == user.id

    def test_duplicate_favorite_blocked(self, auth_client):
        auth_client.post('/api/favorite-cities/', {'city': 'Cairo, Egypt'})
        response = auth_client.post('/api/favorite-cities/', {'city': 'Cairo, Egypt'})
        assert response.status_code == 400

    def test_list_only_returns_own_favorites(self, api_client, user, other_user):
        FavoriteCityHelper = __import__('weather.models', fromlist=['FavoriteCity']).FavoriteCity
        FavoriteCityHelper.objects.create(user=user, city='Cairo, Egypt')
        FavoriteCityHelper.objects.create(user=other_user, city='Luxor, Egypt')

        api_client.force_authenticate(user=user)
        response = api_client.get('/api/favorite-cities/')
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['city'] == 'Cairo, Egypt'

    def test_delete_favorite(self, auth_client):
        create_response = auth_client.post('/api/favorite-cities/', {'city': 'Cairo, Egypt'})
        favorite_id = create_response.data['id']
        response = auth_client.delete(f'/api/favorite-cities/{favorite_id}/')
        assert response.status_code == 204

    def test_no_update_action_available(self, auth_client):
        create_response = auth_client.post('/api/favorite-cities/', {'city': 'Cairo, Egypt'})
        favorite_id = create_response.data['id']
        response = auth_client.patch(f'/api/favorite-cities/{favorite_id}/', {'city': 'Luxor, Egypt'})
        assert response.status_code == 405