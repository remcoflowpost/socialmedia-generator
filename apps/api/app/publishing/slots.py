"""Planningsrekenwerk in de tijdzone van het bedrijf. Tijdstippen gaan erin en eruit als
UTC-instant; lokale tijden verlaten deze module nooit zonder hun zone."""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
MIN_LEAD = timedelta(minutes=1)


@dataclass(frozen=True)
class Slot:
    weekday: int  # ISO 1 = maandag
    local_time: str  # "HH:MM"


def is_valid_timezone(name: str) -> bool:
    if not name or len(name) > 64:
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return name in available_timezones() or name == "UTC"


def parse_time(text: str) -> time | None:
    match = _TIME.match((text or "").strip())
    return time(int(match[1]), int(match[2])) if match else None


class LocalTimeError(ValueError):
    pass


def resolve_local(day: date, at: time, zone: str, *, strict: bool = True) -> datetime:
    """Lokale datum + tijd naar UTC-instant.

    Bestaat de tijd niet (zomertijd begint), dan geeft strict een fout en schuift een
    terugkerend slot naar voren. Een dubbele tijd (wintertijd) wordt het eerste moment.
    """
    tz = ZoneInfo(zone)
    local = datetime.combine(day, at, tzinfo=tz).replace(fold=0)
    roundtrip = local.astimezone(UTC).astimezone(tz)
    if (roundtrip.hour, roundtrip.minute, roundtrip.date()) != (at.hour, at.minute, day):
        if strict:
            raise LocalTimeError(
                f"{at:%H:%M} bestaat niet op {day:%d-%m-%Y} in {zone} (klok gaat vooruit). "
                "Kies een andere tijd."
            )
        return roundtrip.astimezone(UTC)  # naar het eerstvolgende bestaande moment
    return local.astimezone(UTC)


def week_start(zone: str, ref: datetime | date | None = None) -> date:
    tz = ZoneInfo(zone)
    if ref is None:
        ref = datetime.now(UTC)
    local_day = ref.astimezone(tz).date() if isinstance(ref, datetime) else ref
    return local_day - timedelta(days=local_day.isoweekday() - 1)


def slot_instants_between(slots: list[Slot], zone: str, start: datetime, end: datetime) -> list:
    tz = ZoneInfo(zone)
    out: set[datetime] = set()
    day = start.astimezone(tz).date()
    last = end.astimezone(tz).date()
    while day <= last:
        for slot in slots:
            parsed = parse_time(slot.local_time)
            if slot.weekday != day.isoweekday() or not parsed:
                continue
            instant = resolve_local(day, parsed, zone, strict=False)
            if start <= instant < end:
                out.add(instant)
        day += timedelta(days=1)
    return sorted(out)


def next_open_slot(
    slots: list[Slot], zone: str, occupied: set[datetime], now: datetime, horizon_days: int = 56
) -> datetime | None:
    if not slots:
        return None
    candidates = slot_instants_between(
        slots, zone, now + MIN_LEAD, now + timedelta(days=horizon_days)
    )
    return next((c for c in candidates if c not in occupied), None)
