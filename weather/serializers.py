from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import FavoriteCity, WeatherRecord
from rest_framework.validators import UniqueTogetherValidator


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class WeatherRecordSerializer(serializers.ModelSerializer):
    temperature_diff = serializers.SerializerMethodField()

    class Meta:
        model = WeatherRecord
        fields = '__all__'
        read_only_fields = ['source']

    def get_temperature_diff(self, obj: WeatherRecord) -> float | None:
        previous = WeatherRecord.objects.filter(
            city=obj.city,
            recorded_at__lt=obj.recorded_at
        ).first()
        if previous is None:
            return None
        return round(obj.temperature - previous.temperature, 2)

class FavoriteCitySerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteCity
        fields = ['id', 'user', 'city']
        read_only_fields = ['user']
