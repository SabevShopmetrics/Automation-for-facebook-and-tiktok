"""Време в София (EET/EEST) без външни библиотеки.

Windows често няма tzdata, затова прилагаме правилото на ЕС директно:
лятно часово време от последната неделя на март 01:00 UTC
до последната неделя на октомври 01:00 UTC.
"""
from datetime import datetime, timedelta, timezone

FORMAT = "%Y-%m-%d %H:%M"


def _last_sunday(year: int, month: int) -> datetime:
    if month == 12:
        last = datetime(year, 12, 31)
    else:
        last = datetime(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def offset(utc_dt: datetime) -> timedelta:
    y = utc_dt.year
    start = _last_sunday(y, 3).replace(hour=1, tzinfo=timezone.utc)
    end = _last_sunday(y, 10).replace(hour=1, tzinfo=timezone.utc)
    return timedelta(hours=3 if start <= utc_dt < end else 2)


def parse_local(text: str) -> datetime:
    """'2026-10-28 19:00' (софийско време) -> UTC datetime."""
    naive = datetime.strptime(text.strip(), FORMAT)
    for hours in (2, 3):
        utc = (naive - timedelta(hours=hours)).replace(tzinfo=timezone.utc)
        if offset(utc) == timedelta(hours=hours):
            return utc
    return (naive - timedelta(hours=2)).replace(tzinfo=timezone.utc)


def to_local(utc_dt: datetime) -> str:
    return (utc_dt + offset(utc_dt)).strftime(FORMAT)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
