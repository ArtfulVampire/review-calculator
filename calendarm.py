import datetime as dt
import typing as tp

import storage

# TODO deal with timezone
# 11 am in Moscow
_WORK_BEGIN = dt.time(hour=8, tzinfo=dt.timezone.utc)
# 20 pm in Moscow
_WORK_END = dt.time(hour=17, tzinfo=dt.timezone.utc)

_HOLIDAYS = {
    dt.date(year=2020, month=6, day=24),
    dt.date(year=2020, month=7, day=1),
    dt.date(year=2020, month=11, day=4),
    dt.date(year=2020, month=12, day=31),
    dt.date(year=2021, month=1, day=1),
    dt.date(year=2021, month=1, day=2),
    dt.date(year=2021, month=1, day=3),
    dt.date(year=2021, month=1, day=4),
    dt.date(year=2021, month=1, day=5),
    dt.date(year=2021, month=1, day=6),
    dt.date(year=2021, month=1, day=7),
    dt.date(year=2021, month=2, day=22),
    dt.date(year=2021, month=2, day=23),
    dt.date(year=2021, month=3, day=8),
    dt.date(year=2021, month=5, day=1),
    dt.date(year=2021, month=5, day=9),
    dt.date(year=2021, month=6, day=12),
    dt.date(year=2021, month=11, day=4),
}

# TODO - copy from working calendar
_WORKING_WEEKENDS: tp.Set[dt.date] = {dt.date(year=2021, month=2, day=20)}


def _is_holiday(tim: dt.datetime) -> bool:
    return (
        tim.weekday() in [5, 6] and tim.date() not in _WORKING_WEEKENDS
    ) or tim.date() in _HOLIDAYS


async def is_working_day(
        input_time: dt.datetime, staff_login: str, ctx,
) -> bool:
    if _is_holiday(input_time):
        return False

    utc = input_time.astimezone(dt.timezone.utc).replace(tzinfo=None)
    gaps = await storage.get_gaps(staff_login, ctx.conn)
    for (begin, end) in gaps:
        if begin <= utc <= end:
            return False

    return True


def nearest_working_time(input_time: dt.datetime) -> dt.datetime:
    result = input_time.astimezone(dt.timezone.utc)

    # TODO go to storage and check gaps

    if result.timetz() > _WORK_END or _is_holiday(result):  # is_working_day
        result = result.replace(
            hour=_WORK_BEGIN.hour, minute=0, second=0, microsecond=0,
        ) + dt.timedelta(days=1)

    elif result.timetz() < _WORK_BEGIN:
        result = result.replace(
            hour=_WORK_BEGIN.hour, minute=0, second=0, microsecond=0,
        )

    while _is_holiday(result):  # TODO is_working_day
        result += dt.timedelta(days=1)

    return result


def get_working_time_between(
        begin_at: dt.datetime, end_at: dt.datetime, reviewer: str,
) -> dt.timedelta:
    begin = nearest_working_time(begin_at)
    end = nearest_working_time(end_at)

    result: dt.timedelta = dt.timedelta()
    while begin.date() != end.date():
        begin += dt.timedelta(days=1)
        if not _is_holiday(begin):  # TODO is_working_day
            result += dt.timedelta(hours=9)  # full working day

    result += end - begin
    return result


def get_week_start_date(tim: dt.datetime) -> dt.date:
    return (tim - dt.timedelta(days=tim.weekday())).date()


def get_week_start_datetime(tim: dt.datetime) -> dt.datetime:
    return dt.datetime.combine(date=get_week_start_date(tim), time=dt.time())
