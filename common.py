import datetime as dt
import logging
import typing as tp


REPOS = {
    'roovvy': [
        'sdc',
    ],
}

logger = logging.getLogger()


def secs_to_next_round(
        delta: dt.timedelta, offset: dt.timedelta = dt.timedelta(),
) -> float:
    now = dt.datetime.now().time()

    now_delta = dt.timedelta(
        hours=now.hour,
        minutes=now.minute,
        seconds=now.second,
        microseconds=now.microsecond,
    )
    sleep = delta - now_delta % delta + offset

    result = sleep.total_seconds() or (delta + offset).total_seconds()
    logger.debug(f'sleep secs {result}')
    return result


def seconds_till(
        *,
        # all start from zero
        weekday: tp.Optional[int] = None,
        hour: tp.Optional[int] = None,
        minute: int = 0,
) -> float:
    datenow = dt.datetime.now()  # TODO timezone
    logger.debug(
        f'day = {datenow.day}'
        f', hour = {datenow.hour}'
        f', minute = {datenow.minute}',
    )
    till = datenow
    if weekday is not None:
        now_tuple = (datenow.weekday(), datenow.time())
        then_tuple = (weekday, dt.time(hour or 11, minute, 0, 0))
        if now_tuple > then_tuple:
            # move to the corresponding weekday (next week)
            till += dt.timedelta(days=7 - till.weekday() + weekday)
        else:
            till += dt.timedelta(days=weekday - datenow.weekday())

        logger.debug(f'day1: till = {till}')
        till = till.replace(
            hour=hour or 11, minute=minute, second=0, microsecond=0,  # TODO
        )
        logger.debug(f'day2: till = {till}')
    elif hour is not None:
        if datenow.time() > dt.time(hour or 11, minute, 0, 0):
            # move to the corresponding hour (next day)
            till += dt.timedelta(hours=24 - till.hour + hour)

        logger.debug(f'hour1: till = {till}')
        till = till.replace(hour=hour, minute=minute, second=0, microsecond=0)
        logger.debug(f'hour2: till = {till}')
    elif minute is not None:
        if dt.time(0, minute) < datenow.time().replace(hour=0):
            # move to the corresponding minute (next hour)
            till += dt.timedelta(minutes=60 - till.minute + minute)

        logger.debug(f'minute1: till = {till}')
        till = till.replace(minute=minute, second=0, microsecond=0)
        logger.debug(f'minute2: till = {till}')

    result = (till - datenow).total_seconds()
    logger.debug(f'till = {till}, seconds_to_sleep = {result}')
    return result
