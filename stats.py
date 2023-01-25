import datetime as dt
import logging
import statistics as stat
import typing as tp

import calendarm
import events
import github
import storage


logger = logging.getLogger()


def _convert_to_events(
        pr_events: tp.List[tp.Dict], author: str,
) -> tp.List[events.Event]:
    result: tp.List[events.Event] = []

    for event in pr_events:
        my_event = events.Event(event, author)
        if my_event.is_ok:
            result.append(my_event)
            if my_event.is_terminal:
                break

    return result


async def _get_review_events(
        pull_request: github.PullRequest, ctx,
) -> tp.List[events.Event]:
    author, pr_events = await github.get_timeline(pull_request, ctx)

    result: tp.List[events.Event] = _convert_to_events(pr_events, author)

    return result


# reviewer_name -> minutes
async def _get_review_times(
        pull_request: github.PullRequest, ctx,
) -> tp.Dict[str, tp.List[tp.Dict]]:
    result: tp.Dict[
        str, tp.List[tp.Dict],
    ] = {}  # reviewer_login -> [{minutes: elapsed, review_at: submitted}, ...]
    stacks: tp.Dict[str, dt.datetime] = {}  # reviewer_login -> last_requested

    review_events = await _get_review_events(pull_request, ctx)

    for event in review_events:
        if not event or not event.reviewer:
            continue
        if event.is_requested:
            # it may be already there, will replace
            stacks[event.reviewer] = event.event_at

        if event.is_removed:
            # keep silence if it's not there
            stacks.pop(event.reviewer, None)

        if event.is_reviewed:
            begin = stacks.pop(event.reviewer, None)
            if begin:
                review_time: dt.timedelta = calendarm.get_working_time_between(
                    begin, event.event_at, event.reviewer,
                )
                review_minutes = review_time // dt.timedelta(minutes=1)
                if review_minutes == 0:
                    logger.info(
                        f'non-working-time review from {event.reviewer} '
                        f'on {pull_request.get_short_slug()}, excluded',
                    )
                    continue
                if (
                        review_minutes < 15 or review_minutes > 5 * 9 * 60
                ):  # config
                    logger.info(
                        f'outlier from {event.reviewer} '
                        f'on {pull_request.get_short_slug()} : '
                        f'{review_minutes} minutes',
                    )
                    continue
                if event.reviewer not in result:
                    result[event.reviewer] = []
                result[event.reviewer].append(
                    {'minutes': review_minutes, 'review_at': event.event_at},
                )
            else:
                logger.info(
                    f'non-requested review from {event.reviewer} '
                    f'on {pull_request.get_short_slug()}',
                )

    return result


async def get_review_stats(
        pull_request: github.PullRequest, ctx,
) -> tp.List[tp.Dict]:
    result: tp.List[tp.Dict] = []
    review_times = await _get_review_times(pull_request, ctx)
    for reviewer, reviews in review_times.items():
        for review in reviews:
            result.append(
                {
                    'reviewer': reviewer,
                    'minutes': review['minutes'],
                    'review_at': review['review_at'],
                },
            )
    return result


def _calculate_stats(times: tp.List[int]) -> dict:
    result: dict = {}
    result['mean'] = stat.mean(times)
    result['median'] = stat.median(times)
    result['sigma'] = stat.stdev(times)
    result['number'] = len(times)
    return result


async def get_stats_to_show(
        staff_login: str, date_from: dt.datetime, date_to: dt.datetime, ctx,
) -> tp.Optional[dict]:
    times: tp.List[int] = await storage.get_times(
        staff_login, date_from, date_to, ctx.conn,
    )
    logger.debug(f'{staff_login}: len(times) = {len(times)}')
    if len(times) < 2:
        return None

    result = _calculate_stats(times)
    logger.debug(f'{staff_login}: stats = {result}')

    return result


# TODO improve
async def get_subordinated_stats_to_show(
        subordinates: tp.Iterable[str],
        date_from: dt.datetime,
        date_to: dt.datetime,
        ctx,
) -> dict:
    result: dict = {}
    for sub in sorted(subordinates):
        stats = await get_stats_to_show(sub, date_from, date_to, ctx)
        if stats:
            result[sub] = stats

    return result
