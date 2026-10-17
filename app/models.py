
from typing import Literal

from pydantic import BaseModel, Field


class IntentClassification(BaseModel):
    """Classify the request and extract routing information."""

    intent: Literal["research", "weather", "trip", "general"]
    destination: str | None = None
    duration_days: int | None = Field(default=None, ge=1, le=30)
    needs_weather: bool = False
    reasoning: str


class ResearchSource(BaseModel):
    title: str
    url: str
    summary: str = ""


class ResearchResult(BaseModel):
    query: str
    findings: str
    sources: list[ResearchSource] = Field(default_factory=list)
    status: Literal["success", "failed"] = "success"
    error: str | None = None


class WeatherResult(BaseModel):
    city: str
    temperature: float | None = None
    feels_like: float | None = None
    humidity: int | None = None
    conditions: str | None = None
    wind_speed: float | None = None
    units: str = "metric"
    status: Literal["success", "failed"] = "success"
    error: str | None = None


class ItineraryDay(BaseModel):
    day: int = Field(ge=1)
    activities: list[str]
    notes: list[str] = Field(default_factory=list)


class ItineraryPlan(BaseModel):
    destination: str
    duration_days: int = Field(ge=1, le=30)
    days: list[ItineraryDay]
    estimated_budget: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    approved: bool
    final_answer: str
    issues: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
