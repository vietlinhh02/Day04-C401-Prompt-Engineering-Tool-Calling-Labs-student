from __future__ import annotations

from typing import Any

from tools._shared import err


def weather_mock(city: str = "", day: str = "today", units: str = "C") -> dict[str, Any]:
    """
    Mock weather tool (no external API).
    Useful for testing routing and argument extraction without network/env keys.
    """
    try:
        city = (city or "").strip()
        if not city:
            raise ValueError("Missing city")
        day = (day or "today").strip().lower()
        units = (units or "C").strip().upper()
        if units not in {"C", "F"}:
            raise ValueError("units must be 'C' or 'F'")
        if day not in {"today", "tomorrow"}:
            raise ValueError("day must be 'today' or 'tomorrow'")

        temp = 31 if units == "C" else 88
        return {
            "tool": "weather_mock",
            "city": city,
            "day": day,
            "units": units,
            "forecast": {
                "condition": "partly_cloudy",
                "temperature": temp,
                "precip_probability": 0.2,
            },
        }
    except Exception as exc:
        return err("weather_mock", exc)
