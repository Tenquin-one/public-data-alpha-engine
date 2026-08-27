from __future__ import annotations

from datetime import date
from typing import Any


# Official 2026 calendar basis, augmented for the 2026 Labour Day and
# Constitution Day restorations. The Seed's initial 90-day window is fully
# covered; unknown future years deliberately return no named holiday.
HOLIDAYS_2026 = {
    "2026-01-01": "New Year's Day",
    "2026-02-16": "Seollal holiday",
    "2026-02-17": "Seollal",
    "2026-02-18": "Seollal holiday",
    "2026-03-01": "Independence Movement Day",
    "2026-03-02": "Substitute holiday (Independence Movement Day)",
    "2026-05-01": "Labour Day",
    "2026-05-05": "Children's Day",
    "2026-05-24": "Buddha's Birthday",
    "2026-05-25": "Substitute holiday (Buddha's Birthday)",
    "2026-06-03": "Nationwide local elections",
    "2026-06-06": "Memorial Day",
    "2026-07-17": "Constitution Day",
    "2026-08-15": "Liberation Day",
    "2026-08-17": "Substitute holiday (Liberation Day)",
    "2026-09-24": "Chuseok holiday",
    "2026-09-25": "Chuseok",
    "2026-09-26": "Chuseok holiday",
    "2026-10-03": "National Foundation Day",
    "2026-10-05": "Substitute holiday (National Foundation Day)",
    "2026-10-09": "Hangul Day",
    "2026-12-25": "Christmas Day",
}


def calendar_features(value: date) -> dict[str, Any]:
    holiday_name = HOLIDAYS_2026.get(value.isoformat())
    month = value.month
    season = (
        "winter"
        if month in {12, 1, 2}
        else "spring"
        if month in {3, 4, 5}
        else "summer"
        if month in {6, 7, 8}
        else "autumn"
    )
    return {
        "local_date": value.isoformat(),
        "weekday_iso": value.isoweekday(),
        "weekday_name": value.strftime("%A"),
        "is_weekend": value.isoweekday() >= 6,
        "is_holiday": holiday_name is not None,
        "holiday_name": holiday_name,
        "season": season,
        "holiday_calendar_version": "kr-official-2026-v1",
    }
