import logging
from typing import Optional, Tuple
import httpx

from fashion_pipeline.db.models import User
from fashion_pipeline.schemas.context import (
    ContextQuestion,
    ContextQuestionnaireResponse,
    DressingContext,
    DressingContextRequest,
    FormalityLevel,
    OccasionType,
    QuestionOption,
    StyleMood,
    TimeSetting,
    WeatherCondition,
)

logger = logging.getLogger(__name__)


class ContextGatheringService:
    """Service that provides context questions and resolves dressing requirements."""

    def __init__(self, http_timeout: float = 2.0):
        self.http_timeout = http_timeout

    def get_questionnaire(self) -> ContextQuestionnaireResponse:
        """Return the five structured context questions and selectable options."""
        questions = [
            ContextQuestion(
                id="occasion",
                title="Occasion",
                prompt="Select the occasion or planned activity.",
                options=[
                    QuestionOption(id="work_office", label="Work and Office", description="Corporate or desk environment"),
                    QuestionOption(id="casual_daily", label="Casual Daily", description="Daily activities and errands"),
                    QuestionOption(id="date_night", label="Date Night", description="Dinner or evening social event"),
                    QuestionOption(id="formal_event", label="Formal Event", description="Gala or official celebration"),
                    QuestionOption(id="workout_active", label="Workout and Active", description="Fitness and sports"),
                    QuestionOption(id="outdoor_travel", label="Outdoor and Travel", description="Sightseeing and movement"),
                    QuestionOption(id="party_social", label="Party and Social", description="Nightlife or celebration"),
                    QuestionOption(id="home_lounge", label="Home and Lounge", description="Relaxed indoor setting"),
                ],
            ),
            ContextQuestion(
                id="formality",
                title="Formality Level",
                prompt="Select the required level of dress formality.",
                options=[
                    QuestionOption(id="ultra_casual", label="Ultra Casual", description="Athleisure and loungewear"),
                    QuestionOption(id="smart_casual", label="Smart Casual", description="Neat everyday clothing"),
                    QuestionOption(id="business_casual", label="Business Casual", description="Office standard wear"),
                    QuestionOption(id="business_formal", label="Business Formal", description="Suits and tailored dresses"),
                    QuestionOption(id="semi_formal", label="Semi Formal", description="Cocktail and elegant evening wear"),
                    QuestionOption(id="black_tie", label="Black Tie", description="Formal evening wear"),
                ],
            ),
            ContextQuestion(
                id="weather",
                title="Weather Condition",
                prompt="Select ambient weather condition or let system check live forecast.",
                options=[
                    QuestionOption(id="hot", label="Hot", description="Above 28 degrees Celsius"),
                    QuestionOption(id="warm", label="Warm", description="Between 20 and 28 degrees Celsius"),
                    QuestionOption(id="mild", label="Mild", description="Between 12 and 20 degrees Celsius"),
                    QuestionOption(id="cold", label="Cold", description="Between 3 and 12 degrees Celsius"),
                    QuestionOption(id="freezing", label="Freezing", description="Below 3 degrees Celsius"),
                    QuestionOption(id="rainy", label="Rainy", description="Precipitation or wet conditions"),
                ],
            ),
            ContextQuestion(
                id="time_setting",
                title="Time and Setting",
                prompt="Select time of day and primary venue setting.",
                options=[
                    QuestionOption(id="daytime_indoors", label="Daytime Indoors", description="Day hours in temperature controlled room"),
                    QuestionOption(id="daytime_outdoors", label="Daytime Outdoors", description="Day hours with ambient exposure"),
                    QuestionOption(id="evening_indoors", label="Evening Indoors", description="Evening hours inside venue"),
                    QuestionOption(id="evening_outdoors", label="Evening Outdoors", description="Evening hours outside"),
                    QuestionOption(id="all_day_mixed", label="All-day Mixed", description="Mixed indoor and outdoor movement"),
                ],
            ),
            ContextQuestion(
                id="style_mood",
                title="Style Mood",
                prompt="Select desired visual impression and mood.",
                options=[
                    QuestionOption(id="clean_minimalist", label="Clean Minimalist", description="Simple lines and neutral palette"),
                    QuestionOption(id="bold_expressive", label="Bold and Expressive", description="Eye catching colors and strong patterns"),
                    QuestionOption(id="relaxed_comfort", label="Relaxed Comfort", description="Loose fits and soft fabrics"),
                    QuestionOption(id="sharp_tailored", label="Sharp Tailored", description="Structured silhouettes and crisp collars"),
                    QuestionOption(id="no_preference", label="No Preference", description="Any balanced combination"),
                ],
            ),
        ]
        return ContextQuestionnaireResponse(questions=questions)

    async def fetch_weather_from_open_meteo(
        self,
        city: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Tuple[Optional[WeatherCondition], Optional[float], Optional[str]]:
        """Fetch current weather from Open-Meteo API with fallback."""
        resolved_lat = latitude
        resolved_lon = longitude
        source_desc = None

        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                if (resolved_lat is None or resolved_lon is None) and city:
                    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
                    geo_res = await client.get(geo_url)
                    if geo_res.status_code == 200:
                        geo_data = geo_res.json()
                        results = geo_data.get("results")
                        if results and len(results) > 0:
                            resolved_lat = float(results[0]["latitude"])
                            resolved_lon = float(results[0]["longitude"])
                            source_desc = f"open-meteo:{city}"

                if resolved_lat is not None and resolved_lon is not None:
                    weather_url = (
                        f"https://api.open-meteo.com/v1/forecast"
                        f"?latitude={resolved_lat}&longitude={resolved_lon}&current=temperature_2m,weather_code"
                    )
                    w_res = await client.get(weather_url)
                    if w_res.status_code == 200:
                        w_data = w_res.json()
                        current = w_data.get("current", {})
                        temp = current.get("temperature_2m")
                        code = current.get("weather_code")
                        condition = self._map_open_meteo_to_condition(temp, code)
                        source = source_desc or f"open-meteo:({resolved_lat:.2f},{resolved_lon:.2f})"
                        return condition, temp, source

        except Exception as exc:
            logger.warning(f"Could not retrieve weather from Open-Meteo: {exc}. Using fallback.")

        return None, None, None

    def _map_open_meteo_to_condition(
        self,
        temperature: Optional[float],
        weather_code: Optional[int],
    ) -> WeatherCondition:
        """Map Open-Meteo numeric temperature and WMO weather codes to WeatherCondition."""
        rain_codes = {51, 53, 55, 61, 63, 65, 80, 81, 82}
        if weather_code in rain_codes:
            return WeatherCondition.RAINY

        if temperature is None:
            return WeatherCondition.MILD

        if temperature > 28.0:
            return WeatherCondition.HOT
        if temperature >= 20.0:
            return WeatherCondition.WARM
        if temperature >= 12.0:
            return WeatherCondition.MILD
        if temperature >= 3.0:
            return WeatherCondition.COLD
        return WeatherCondition.FREEZING

    def _infer_default_formality(self, occasion: OccasionType) -> FormalityLevel:
        """Infer target formality level when user does not specify one."""
        mapping = {
            OccasionType.WORK_OFFICE: FormalityLevel.BUSINESS_CASUAL,
            OccasionType.CASUAL_DAILY: FormalityLevel.SMART_CASUAL,
            OccasionType.DATE_NIGHT: FormalityLevel.SMART_CASUAL,
            OccasionType.FORMAL_EVENT: FormalityLevel.BUSINESS_FORMAL,
            OccasionType.WORKOUT_ACTIVE: FormalityLevel.ULTRA_CASUAL,
            OccasionType.OUTDOOR_TRAVEL: FormalityLevel.SMART_CASUAL,
            OccasionType.PARTY_SOCIAL: FormalityLevel.SMART_CASUAL,
            OccasionType.HOME_LOUNGE: FormalityLevel.ULTRA_CASUAL,
        }
        return mapping.get(occasion, FormalityLevel.SMART_CASUAL)

    async def resolve_context(
        self,
        request: DressingContextRequest,
        user: Optional[User] = None,
    ) -> DressingContext:
        """Resolve full dressing context from request parameters and user preferences."""
        occasion = request.occasion or OccasionType.CASUAL_DAILY
        formality = request.formality or self._infer_default_formality(occasion)
        time_setting = request.time_setting or TimeSetting.DAYTIME_INDOORS

        style_mood = request.style_mood
        if style_mood is None or style_mood == StyleMood.NO_PREFERENCE:
            if user and user.default_style:
                try:
                    style_mood = StyleMood(user.default_style)
                except ValueError:
                    style_mood = StyleMood.CLEAN_MINIMALIST
            else:
                style_mood = StyleMood.CLEAN_MINIMALIST

        weather = request.weather
        temp_c = None
        weather_source = None

        if weather is None:
            target_city = request.city or (user.default_city if user else None)
            condition, fetched_temp, source = await self.fetch_weather_from_open_meteo(
                city=target_city,
                latitude=request.latitude,
                longitude=request.longitude,
            )
            if condition is not None:
                weather = condition
                temp_c = fetched_temp
                weather_source = source
            else:
                weather = WeatherCondition.MILD
                weather_source = "fallback_mild"
        else:
            weather_source = "user_selection"

        return DressingContext(
            occasion=occasion,
            formality=formality,
            weather=weather,
            time_setting=time_setting,
            style_mood=style_mood,
            resolved_temperature_c=temp_c,
            resolved_weather_source=weather_source,
        )
