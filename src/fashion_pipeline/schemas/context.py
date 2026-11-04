from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class OccasionType(str, Enum):
    """Occasion types for dressing context."""

    WORK_OFFICE = "work_office"
    CASUAL_DAILY = "casual_daily"
    DATE_NIGHT = "date_night"
    FORMAL_EVENT = "formal_event"
    WORKOUT_ACTIVE = "workout_active"
    OUTDOOR_TRAVEL = "outdoor_travel"
    PARTY_SOCIAL = "party_social"
    HOME_LOUNGE = "home_lounge"


class FormalityLevel(str, Enum):
    """Target formality levels."""

    ULTRA_CASUAL = "ultra_casual"
    SMART_CASUAL = "smart_casual"
    BUSINESS_CASUAL = "business_casual"
    BUSINESS_FORMAL = "business_formal"
    SEMI_FORMAL = "semi_formal"
    BLACK_TIE = "black_tie"


class WeatherCondition(str, Enum):
    """Ambient weather conditions."""

    HOT = "hot"
    WARM = "warm"
    MILD = "mild"
    COLD = "cold"
    FREEZING = "freezing"
    RAINY = "rainy"


class TimeSetting(str, Enum):
    """Time and venue environment settings."""

    DAYTIME_INDOORS = "daytime_indoors"
    DAYTIME_OUTDOORS = "daytime_outdoors"
    EVENING_INDOORS = "evening_indoors"
    EVENING_OUTDOORS = "evening_outdoors"
    ALL_DAY_MIXED = "all_day_mixed"


class StyleMood(str, Enum):
    """Subjective style mood preference."""

    CLEAN_MINIMALIST = "clean_minimalist"
    BOLD_EXPRESSIVE = "bold_expressive"
    RELAXED_COMFORT = "relaxed_comfort"
    SHARP_TAILORED = "sharp_tailored"
    NO_PREFERENCE = "no_preference"


class QuestionOption(BaseModel):
    """Selectable option for a context question."""

    id: str
    label: str
    description: Optional[str] = None


class ContextQuestion(BaseModel):
    """Context questionnaire item."""

    id: str
    title: str
    prompt: str
    options: List[QuestionOption]


class ContextQuestionnaireResponse(BaseModel):
    """Five context questionnaire items for user interface."""

    questions: List[ContextQuestion]


class DressingContextRequest(BaseModel):
    """User request for outfit context resolution."""

    occasion: Optional[OccasionType] = None
    formality: Optional[FormalityLevel] = None
    weather: Optional[WeatherCondition] = None
    time_setting: Optional[TimeSetting] = None
    style_mood: Optional[StyleMood] = None
    city: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)


class DressingContext(BaseModel):
    """Resolved context used by recommendation engine."""

    occasion: OccasionType
    formality: FormalityLevel
    weather: WeatherCondition
    time_setting: TimeSetting
    style_mood: StyleMood
    resolved_temperature_c: Optional[float] = None
    resolved_weather_source: Optional[str] = None
