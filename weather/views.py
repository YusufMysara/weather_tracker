import json
from rest_framework import mixins, viewsets
from .models import FavoriteCity, WeatherRecord
from .serializers import WeatherRecordSerializer
import openpyxl
from django.http import HttpResponse
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import RegisterSerializer, FavoriteCitySerializer
import google.generativeai as genai
from django.conf import settings
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.db.models import Avg
from django.utils import timezone
from django.db import connection
from datetime import timedelta
import requests
from django.db.models import Avg, Max, Min
from rest_framework.exceptions import ValidationError



genai.configure(api_key=settings.GEMINI_API_KEY)

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

class WeatherViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = WeatherRecordSerializer

    def get_queryset(self):
        city = self.request.query_params.get('city')
        if city:
            return WeatherRecord.objects.filter(city=city)
        return WeatherRecord.objects.all()
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action == 'export':
            self.throttle_scope = 'export'
            return [ScopedRateThrottle()]
        if self.action in ['insights', 'forecast', 'ask', 'compare']:
            self.throttle_scope = 'ai'
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=['get'])
    def export(self, request):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Weather Records"

        sheet.append(['City', 'Temperature', 'Humidity', 'Wind Speed', 'Recorded At', 'Source'])

        for record in self.get_queryset():
            sheet.append([
                record.city,
                record.temperature,
                record.humidity,
                record.wind_speed,
                record.recorded_at.strftime('%Y-%m-%d %H:%M'),
                record.source,
            ])

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="weather_records.xlsx"'
        workbook.save(response)
        return response


    @extend_schema(
        parameters=[
            OpenApiParameter(name='city', type=str, location=OpenApiParameter.QUERY, required=True),
        ]
    )
    @action(detail=False, methods=['get'])
    def insights(self, request):
        city = request.query_params.get('city')
        if not city:
            return Response({"error": "city query parameter is required"}, status=400)

        records = WeatherRecord.objects.filter(city=city)[:10]
        if not records:
            return Response({"error": "no records found for this city"}, status=404)

        lines = [
            f"{r.recorded_at.strftime('%Y-%m-%d %H:%M')} - "
            f"temp: {r.temperature}°C, humidity: {r.humidity}%, wind: {r.wind_speed} km/h"
            for r in records
        ]
        data_text = "\n".join(lines)

        seven_days_ago = timezone.now() - timedelta(days=7)
        weekly = WeatherRecord.objects.filter(city=city, recorded_at__gte=seven_days_ago)
        weekly_stats = weekly.aggregate(
            avg_temp=Avg('temperature'),
            avg_humidity=Avg('humidity'),
            avg_wind=Avg('wind_speed'),
        )

        latest = records[0]
        context_text = (
            f"7-day averages for {city}: "
            f"temperature {weekly_stats['avg_temp']}°C, "
            f"humidity {weekly_stats['avg_humidity']}%, "
            f"wind {weekly_stats['avg_wind']} km/h.\n"
            f"Most recent reading: temperature {latest.temperature}°C, "
            f"humidity {latest.humidity}%, wind {latest.wind_speed} km/h."
            if weekly_stats['avg_temp'] is not None
            else "No historical data available yet for comparison."
        )

        prompt = (
            f"Here is recent weather data for {city}, most recent first:\n\n"
            f"{data_text}\n\n"
            f"{context_text}\n\n"
            "Respond ONLY with valid JSON, no markdown formatting, no code fences, "
            "matching exactly this structure:\n"
            '{"summary": "2-3 sentence plain-language trend summary", '
            '"activities": ["activity 1", "activity 2", "activity 3"], '
            '"warnings": ["warning or reassurance"], '
            '"anomaly": "one sentence comparing the current reading to the 7-day average"}\n\n'
            "IMPORTANT: every field must contain real content — never return an empty list or null. "
            "'activities' must always list at least 3 realistic suggestions given the conditions. "
            "'warnings' must always contain at least one item — if there is no genuine safety concern, "
            "instead include a short reassuring statement such as 'No significant weather risks at this time.' "
            "'anomaly' must always contain a comparison sentence — if the reading matches the average closely, "
            "say so explicitly (e.g. 'Consistent with the recent 7-day average, nothing unusual.') rather than leaving it blank."
        )

        model = genai.GenerativeModel('gemini-3.5-flash-lite')
        response = model.generate_content(prompt)

        if not response.text:
            return Response({"error": "AI returned an empty response"}, status=502)

        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError:
            return Response({"error": "AI response could not be parsed"}, status=502)

        return Response({
            "city": city,
            "summary": parsed.get("summary"),
            "activities": parsed.get("activities", []),
            "warnings": parsed.get("warnings", []),
            "anomaly": parsed.get("anomaly"),
        })

    @extend_schema(
        parameters=[
            OpenApiParameter(name='city', type=str, location=OpenApiParameter.QUERY, required=True),
        ]
    )
    @action(detail=False, methods=['get'])
    def forecast(self, request):
        city = request.query_params.get('city')
        if not city:
            return Response({"error": "city query parameter is required"}, status=400)

        coords = settings.WEATHER_CITIES.get(city)
        if not coords:
            return Response({"error": "unknown city"}, status=404)

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": 3,
            "timezone": "auto",
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
        except requests.RequestException:
            return Response({"error": "could not reach weather forecast service"}, status=502)

        daily = response.json()["daily"]

        """
        "daily": {
            "time": ["2026-08-17", "2026-08-18"],
            "temperature_2m_max": [36, 37],
            "temperature_2m_min": [27, 28],
            "precipitation_sum": [0, 2.4]
        }
        """

        forecast_lines = []
        for i in range(len(daily["time"])):
            forecast_lines.append(
                f"{daily['time'][i]}: high {daily['temperature_2m_max'][i]}°C, "
                f"low {daily['temperature_2m_min'][i]}°C, "
                f"precipitation {daily['precipitation_sum'][i]}mm"
            )

        """
        forecast_lines = [
            "2026-08-17: high 36°C, low 27°C, precipitation 0mm",
            "2026-08-18: high 37°C, low 28°C, precipitation 2.4mm",
            "2026-08-19: high 35°C, low 26°C, precipitation 0.8mm"
        ]
        """

        forecast_text = "\n".join(forecast_lines) # convert the list of daily forecast sentences into one multiline string that can easily be inserted into the AI prompt.

        prompt = (
            f"Here is the real 3-day weather forecast for {city}, from a meteorological forecast model:\n\n"
            f"{forecast_text}\n\n"
            "Respond ONLY with valid JSON, no markdown formatting, no code fences, "
            "matching exactly this structure:\n"
            '{"forecast_summary": "2-3 sentence plain-language description of the next 3 days", '
            '"recommendation": "one practical sentence of advice based on this forecast"}\n\n'
            "Base your response strictly on the data given — do not invent numbers or conditions not present in the data."
        )

        model = genai.GenerativeModel('gemini-3.5-flash-lite')
        ai_response = model.generate_content(prompt)

        if not ai_response.text:
            return Response({"error": "AI returned an empty response"}, status=502)

        try:
            parsed = json.loads(ai_response.text)
        except json.JSONDecodeError:
            return Response({"error": "AI response could not be parsed"}, status=502)

        return Response({
            "city": city,
            "raw_forecast": [
                {
                    "date": daily["time"][i],
                    "high": daily["temperature_2m_max"][i],
                    "low": daily["temperature_2m_min"][i],
                    "precipitation_mm": daily["precipitation_sum"][i],
                }
                for i in range(len(daily["time"]))
            ],
            "forecast_summary": parsed.get("forecast_summary"),
            "recommendation": parsed.get("recommendation"),
        })

    @extend_schema(request={'application/json': {'type': 'object', 'properties': {'question': {'type': 'string'}}}},)
    @action(detail=False, methods=['post'])
    def ask(self, request):
        question = request.data.get('question')
        if not question:
            return Response({"error": "question is required"}, status=400)

        city_list = ", ".join(settings.WEATHER_CITIES.keys())

        interpret_prompt = (
            f"A user asked this question about weather data: \"{question}\"\n\n"
            f"Known cities: {city_list}\n\n"
            "This system can ONLY answer questions about temperature, humidity, or wind speed — "
            "as a single latest reading, or a max/min/avg — for one city or all cities. "
            "It has no data on precipitation, forecasts, or explanations of causes.\n\n"
            "If the question fits, convert it into ONLY valid JSON, no markdown, matching exactly this structure:\n"
            '{"scope": "single_city" or "all_cities", '
            '"city": "<one of the known cities, or null if scope is all_cities>", '
            '"metric": "temperature" or "humidity" or "wind_speed", '
            '"aggregation": "latest" or "max" or "min" or "avg"}\n\n'
            "If the question does NOT clearly fit this structure — for example it asks about precipitation, "
            "forecasts, comparisons between specific cities, explanations, or anything unrelated to weather — "
            "respond with EXACTLY this instead: {\"unsupported\": true}\n\n"
            "Do not explain, respond with ONLY one JSON object."
        )
        model = genai.GenerativeModel('gemini-3.5-flash-lite')
        interpret_response = model.generate_content(interpret_prompt)

#never trust the AI's output blindly -> check the output
        try:
            intent = json.loads(interpret_response.text)
        except json.JSONDecodeError:
            return Response({"error": "could not interpret question"}, status=502)
        if intent.get('unsupported'):
            return Response(
            {"error": "This question isn't supported yet. Try asking about temperature, "
            "humidity, or wind speed for a specific city or all tracked cities."},
            status=422
        )
        valid_metrics = {'temperature', 'humidity', 'wind_speed'}
        valid_aggregations = {'latest', 'max', 'min', 'avg'}

        metric = intent.get('metric')
        aggregation = intent.get('aggregation')
        scope = intent.get('scope')
        city = intent.get('city')

        if metric not in valid_metrics or aggregation not in valid_aggregations:
            return Response({"error": "could not map question to a supported query"}, status=422)

        if scope == 'single_city':
            if city not in settings.WEATHER_CITIES:
                return Response({"error": "could not identify a known city in the question"}, status=422)
            queryset = WeatherRecord.objects.filter(city=city)
        else:
            queryset = WeatherRecord.objects.all()

        if aggregation == 'latest':
            record = queryset.first()
            if not record:
                return Response({"error": "no data available"}, status=404)
            result_value = getattr(record, metric)
            result_city = record.city
        else:
            agg_func = {'max': Max, 'min': Min, 'avg': Avg}[aggregation]
            if scope == 'all_cities' and aggregation in ('max', 'min'):
                record = queryset.order_by(
                    f"-{metric}" if aggregation == 'max' else metric
                ).first()
                result_value = getattr(record, metric) if record else None
                result_city = record.city if record else None
            else:
                agg_result = queryset.aggregate(value=agg_func(metric))
                result_value = agg_result['value']
                result_city = city if scope == 'single_city' else 'all tracked cities'
        answer_prompt = (
            f"The user asked: \"{question}\"\n"
            f"The real answer, computed from the database: "
            f"{aggregation} {metric} = {result_value}, for {result_city}.\n\n"
            "Respond with ONLY valid JSON, no markdown:\n"
            '{"answer": "one natural-language sentence directly answering the user\'s question using this exact data"}'
        )

        answer_response = model.generate_content(answer_prompt)

        try:
            final = json.loads(answer_response.text)
        except json.JSONDecodeError:
            return Response({"answer": f"{aggregation} {metric} for {result_city}: {result_value}"})

        return Response({
            "question": question,
            "answer": final.get("answer"),
            "raw_result": {"city": result_city, "metric": metric, "aggregation": aggregation, "value": result_value},
        })

    @extend_schema(
    parameters=[
        OpenApiParameter(name='cities', type=str, location=OpenApiParameter.QUERY,
                        required=True, many=True,
                        description='Repeat this param per city, e.g. ?cities=Cairo, Egypt&cities=Aswan, Egypt'),
    ]
    )
    @action(detail=False, methods=['get'])
    def compare(self, request):
        cities = request.query_params.getlist('cities')

        if len(cities) < 2:
            return Response({"error": "provide at least two cities via ?cities=...&cities=..."}, status=400)

        unknown = [c for c in cities if c not in settings.WEATHER_CITIES]
        if unknown:
            return Response({"error": f"unknown cities: {', '.join(unknown)}"}, status=404)

        results = []
        for city in cities:
            latest = WeatherRecord.objects.filter(city=city).first()
            if latest is None:
                return Response({"error": f"no data available for {city}"}, status=404)
            results.append({
                "city": city,
                "temperature": latest.temperature,
                "humidity": latest.humidity,
                "wind_speed": latest.wind_speed,
                "recorded_at": latest.recorded_at,
            })

        comparison_text = "\n".join(
            f"{r['city']}: {r['temperature']}°C, {r['humidity']}% humidity, {r['wind_speed']} km/h wind"
            for r in results
        )

        prompt = (
            f"Compare these cities' current weather:\n\n{comparison_text}\n\n"
            "Respond ONLY with valid JSON, no markdown:\n"
            '{"comparison": "one or two sentences highlighting the most notable difference(s) between these cities"}'
        )

        model = genai.GenerativeModel('gemini-3.5-flash-lite')
        ai_response = model.generate_content(prompt)

        if not ai_response.text:
            return Response({"error": "AI returned an empty response"}, status=502)

        try:
            parsed = json.loads(ai_response.text)
        except json.JSONDecodeError:
            return Response({"error": "AI response could not be parsed"}, status=502)

        return Response({
            "cities": results,
            "comparison": parsed.get("comparison"),
        })


class FavoriteCityViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteCitySerializer

    def get_queryset(self):
        return self.request.user.favorite_cities.all()

    def perform_create(self, serializer):
        city = serializer.validated_data['city']
        if FavoriteCity.objects.filter(user=self.request.user, city=city).exists():
            raise ValidationError("You have already favorited this city.")
        serializer.save(user=self.request.user)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    try:
        connection.ensure_connection()
        db_status = "ok"
    except Exception as e:
        db_status = f"unreachable: {str(e)}"

    overall_status = "ok" if db_status == "ok" else "degraded"
    status_code = 200 if overall_status == "ok" else 503

    return Response({
        "status": overall_status,
        "database": db_status,
    }, status=status_code)