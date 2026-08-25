from rest_framework.routers import DefaultRouter
from .views import WeatherViewSet, FavoriteCityViewSet

router = DefaultRouter()
router.register('weather', WeatherViewSet, basename='weatherrecord')
router.register('favorite-cities', FavoriteCityViewSet, basename='favoritecity')

urlpatterns = router.urls