import os
from pathlib import Path
import environ
import dj_database_url
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY')
GEMINI_API_KEY = env('GEMINI_API_KEY')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'weather',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '100/hour', 'export': '5/hour', 'ai': '10/hour'},
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Weather Tracker API',
    'DESCRIPTION': 'Weather data with JWT auth, favorites, and AI-generated summaries.',
    'VERSION': '1.0.0',
}

WEATHER_CITIES = {
    "Cairo, Egypt": {"latitude": 30.0444, "longitude": 31.2357},
    "Alexandria, Egypt": {"latitude": 31.2001, "longitude": 29.9187},
    "Giza, Egypt": {"latitude": 30.0131, "longitude": 31.2089},
    "Zagazig, Egypt": {"latitude": 30.5877, "longitude": 31.5022},
    "Mansoura, Egypt": {"latitude": 31.0409, "longitude": 31.3785},
    "Tanta, Egypt": {"latitude": 30.7865, "longitude": 31.0004},
    "Damanhur, Egypt": {"latitude": 31.0341, "longitude": 30.4682},
    "Shibin El Kom, Egypt": {"latitude": 30.5539, "longitude": 31.0119},
    "Banha, Egypt": {"latitude": 30.4667, "longitude": 31.1833},
    "Kafr El Sheikh, Egypt": {"latitude": 31.1107, "longitude": 30.9388},
    "Damietta, Egypt": {"latitude": 31.4165, "longitude": 31.8133},
    "Port Said, Egypt": {"latitude": 31.2653, "longitude": 32.3019},
    "Ismailia, Egypt": {"latitude": 30.5965, "longitude": 32.2715},
    "Suez, Egypt": {"latitude": 29.9668, "longitude": 32.5498},
    "Marsa Matrouh, Egypt": {"latitude": 31.3543, "longitude": 27.2373},
    "El Arish, Egypt": {"latitude": 31.1316, "longitude": 33.7984},
    "El Tor, Egypt": {"latitude": 28.2400, "longitude": 33.6217},
    "Beni Suef, Egypt": {"latitude": 29.0661, "longitude": 31.0994},
    "Faiyum, Egypt": {"latitude": 29.3084, "longitude": 30.8428},
    "Minya, Egypt": {"latitude": 28.1099, "longitude": 30.7503},
    "Asyut, Egypt": {"latitude": 27.1809, "longitude": 31.1837},
    "Sohag, Egypt": {"latitude": 26.5569, "longitude": 31.6948},
    "Qena, Egypt": {"latitude": 26.1551, "longitude": 32.7160},
    "Luxor, Egypt": {"latitude": 25.6872, "longitude": 32.6396},
    "Aswan, Egypt": {"latitude": 24.0889, "longitude": 32.8998},
    "Hurghada, Egypt": {"latitude": 27.2579, "longitude": 33.8116},
    "New Valley (Kharga), Egypt": {"latitude": 25.4514, "longitude": 30.5467},
}

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULE = {
    'fetch-weather-hourly': {
        'task': 'weather.tasks.fetch_weather_data',
        'schedule': timedelta(hours=1),
    },
}