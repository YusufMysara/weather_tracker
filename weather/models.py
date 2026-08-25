from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

class WeatherRecord(models.Model):
    SOURCE_CHOICES = [
        ('api', 'API'),
        ('manual', 'Manual'),
    ]

    city = models.CharField(max_length=50)
    temperature = models.FloatField()
    humidity = models.FloatField()
    wind_speed = models.FloatField()
    recorded_at = models.DateTimeField()
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='api')
    
    class Meta:
        ordering = ['-recorded_at']

    def __str__(self) -> str:
        return f"{self.city} - {self.temperature}°C - {self.source}"


CITY_CHOICES = [(city, city) for city in settings.WEATHER_CITIES.keys()]

class FavoriteCity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_cities')
    city = models.CharField(max_length=50, choices=CITY_CHOICES)

    class Meta:
        unique_together = ('user', 'city')

    def __str__(self) -> str:
        return f"{self.user.username} - {self.city}"