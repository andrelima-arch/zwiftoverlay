import logging
from datetime import date, timedelta

import requests

from app.intervals_icu.auth import AthleteProfile

logger = logging.getLogger(__name__)

BASE_URL = "https://intervals.icu/api/v1"

CYCLING_ACTIVITY_TYPES = {
    "Ride",
    "VirtualRide",
    "MountainBikeRide",
    "GravelRide",
    "TrackRide",
    "Cyclocross",
}


class IntervalsIcuClient:
    def __init__(self, api_key: str, athlete_id: str) -> None:
        self._api_key = api_key
        self._athlete_id = athlete_id
        self._session = requests.Session()
        self._session.auth = ("API_KEY", api_key)
        self._session.headers["Accept"] = "application/json"

    def get_profile(self) -> AthleteProfile | None:
        url = f"{BASE_URL}/athlete/{self._athlete_id}"
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return AthleteProfile(
                id=str(data.get("id", "")),
                name=data.get("name", ""),
                weight_kg=_extract_weight_kg(data),
                ftp=_extract_cycling_ftp(data),
            )
        except requests.RequestException as e:
            logger.error(f"Error fetching profile: {e}")
            return None

    def get_events(self, days_ahead: int = 7, days_back: int = 1) -> list[dict]:
        oldest = (date.today() - timedelta(days=days_back)).isoformat()
        newest = (date.today() + timedelta(days=days_ahead)).isoformat()
        url = f"{BASE_URL}/athlete/{self._athlete_id}/events.json"
        params = {"oldest": oldest, "newest": newest}
        try:
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching events: {e}")
            return []

    def get_event(self, event_id: str) -> dict | None:
        url = f"{BASE_URL}/athlete/{self._athlete_id}/events/{event_id}"
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching event {event_id}: {e}")
            return None

    def get_workout_doc(self, event_id: str) -> dict | None:
        event = self.get_event(event_id)
        if event is None:
            return None
        return event.get("workout_doc")


def _extract_weight_kg(data: dict) -> float | None:
    for key in ("weight", "icu_weight", "weight_kg"):
        value = _parse_float(data.get(key))
        if value is not None:
            return value
    return None


def _extract_cycling_ftp(data: dict) -> int | None:
    for setting in data.get("sportSettings") or []:
        if not isinstance(setting, dict):
            continue
        types = setting.get("types") or []
        if not any(activity_type in CYCLING_ACTIVITY_TYPES for activity_type in types):
            continue
        for key in ("indoor_ftp", "ftp"):
            value = _parse_int(setting.get(key))
            if value is not None:
                return value
        mmp_model = setting.get("mmp_model")
        if isinstance(mmp_model, dict):
            value = _parse_int(mmp_model.get("ftp"))
            if value is not None:
                return value

    for key in ("ftp", "indoor_ftp"):
        value = _parse_int(data.get(key))
        if value is not None:
            return value
    return None


def _parse_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(parsed)
