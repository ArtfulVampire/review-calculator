import datetime as dt
import logging
import typing as tp

import calendarm
import github
import staff
import stats
import storage
import telegram
import user_settings


logger = logging.getLogger()


def _get_period(num_weeks_ago: int) -> tp.Tuple[dt.datetime, dt.datetime]:
    date_from = dt.datetime(2020, 8, 1, 0, 0, 0)
    if num_weeks_ago >= 0:
        date_from = calendarm.get_week_start_datetime(dt.datetime.now())
        date_from -= dt.timedelta(days=7 * num_weeks_ago)

    date_to = dt.datetime.now()
    if 0 <= num_weeks_ago < 5:  # config
        date_to = date_from + dt.timedelta(days=7)
    return date_from, date_to


async def _show_stats(
        staff_login: str, num_weeks_ago: int, chat_id: str, ctx,
) -> None:
    date_from, date_to = _get_period(num_weeks_ago)
    logger.debug(f'{staff_login}: from = {date_from}, to = {date_to}')

    stats_dict = await stats.get_stats_to_show(
        staff_login, date_from, date_to, ctx,
    )
    logger.debug(f'{staff_login}: stats_dict = {stats_dict}')
    if not stats_dict:
        logger.warning(
            f'no stats for {staff_login} in {date_from} - {date_to}',
        )
        await telegram.send_message(telegram.no_stats_message(), chat_id, ctx)
        return

    stats_message: str = telegram.format_single_stats(
        date_from.date().isoformat(), date_to.date().isoformat(), stats_dict,
    )
    if stats_message:
        await telegram.send_message(stats_message, chat_id, ctx)
    else:
        await telegram.send_message(telegram.no_stats_message(), chat_id, ctx)


async def _show_subordinated_stats(
        staff_login: str,
        is_nearest: bool,
        num_weeks_ago: int,
        chat_id: str,
        ctx,
        conn,
) -> None:
    date_from, date_to = _get_period(num_weeks_ago)

    subs_both = await storage.get_subordinated(staff_login, conn)
    if not subs_both:
        await telegram.send_message(telegram.no_stats_message(), chat_id, ctx)
        return
    subs = subs_both[0 if is_nearest else 1]
    if not subs:
        await telegram.send_message(telegram.no_stats_message(), chat_id, ctx)
        return

    stats_dict: dict = await stats.get_subordinated_stats_to_show(
        subs, date_from, date_to, ctx,
    )
    if not stats_dict:
        await telegram.send_message(telegram.no_stats_message(), chat_id, ctx)
        return

    stats_message: str = telegram.format_multiple_stats(
        date_from.date().isoformat(), date_to.date().isoformat(), stats_dict,
    )
    if stats_message:
        # logger.debug(f'stats_message: {stats_message}')
        await telegram.send_message(stats_message, chat_id, ctx)
    else:
        await telegram.send_message(telegram.no_stats_message(), chat_id, ctx)


async def set_notifications(
        staff_login: str, step: int, chat_id: str, ctx,
) -> None:
    if step == 0:
        await user_settings.disable_notifications(staff_login, ctx)
        await telegram.send_message(f'Notifications disabled', chat_id, ctx)
        return

    await user_settings.set_hours(
        range(11, 21, step), staff_login, ctx,  # TODO config, use constants
    )
    await telegram.send_message(
        telegram.notifications_enabled_message(step), chat_id, ctx,
    )


async def _show_reviewed(
        staff_login: str, num_weeks_ago: int, chat_id: str, ctx,
) -> None:
    date_from, date_to = _get_period(num_weeks_ago)

    prs = await github.get_reviewed_prs(
        staff_login, date_from, date_to, None, ctx,
    )
    await telegram.send_message(
        await telegram.show_reviewed_message(prs, staff_login, ctx),
        chat_id,
        ctx,
    )


async def _show_want_review(
        staff_login: str, action_value: int, chat_id: str, ctx, conn,
) -> None:
    authors = await staff.get_fellow_authors(staff_login, action_value, ctx)
    prs = await github.get_open_prs(authors, staff_login, ctx)
    settings = await storage.get_reviewer_settings(staff_login, conn)

    if not settings:
        logger.warning(f'Empty settings for {staff_login}, wipprs = ON')
    elif not settings['wip']:
        prs = [pr for pr in prs if not pr.is_wip]

    msg = (
        await telegram.want_review_message(prs, ctx)
        if prs
        else 'Nothing to review here'
    )
    await telegram.send_message(msg, chat_id, ctx)


async def _myprs(
        staff_login: str, action_value: int, chat_id: str, ctx, conn,
) -> None:
    myprs: bool = action_value == 1
    await storage.set_myprs(myprs, staff_login, conn)
    await telegram.send_message(
        telegram.set_myprs_message(myprs), chat_id, ctx,
    )


async def _wipprs(
        staff_login: str, action_value: int, chat_id: str, ctx, conn,
) -> None:
    wipprs = action_value == 1
    await storage.set_wipprs(wipprs, staff_login, conn)
    await telegram.send_message(
        telegram.set_wipprs_message(wipprs), chat_id, ctx,
    )


async def _startrek(
        staff_login: str, action_value: int, chat_id: str, ctx, conn,
) -> None:
    startrek: bool = action_value == 1
    await storage.set_startrek(startrek, staff_login, conn)
    await telegram.send_message(
        telegram.set_startrek_message(startrek), chat_id, ctx,
    )


async def invoke_callback(
        action_name: str,
        action_value: int,
        staff_login: str,
        chat_id: str,
        ctx,
) -> None:
    async with ctx.pool.acquire() as conn:
        if action_name == 'week':
            await _show_stats(staff_login, action_value, chat_id, ctx)
        elif action_name == 'reviewed':
            await _show_reviewed(staff_login, action_value, chat_id, ctx)
        elif action_name == 'stats_sub_nearest':
            await _show_subordinated_stats(
                staff_login, True, action_value, chat_id, ctx, conn,
            )
        elif action_name == 'stats_sub_all':
            await _show_subordinated_stats(
                staff_login, False, action_value, chat_id, ctx, conn,
            )
        elif action_name == 'notify':
            await set_notifications(staff_login, action_value, chat_id, ctx)
        elif action_name == 'want_review':
            await _show_want_review(
                staff_login, action_value, chat_id, ctx, conn,
            )
        elif action_name == 'myprs':
            await _myprs(staff_login, action_value, chat_id, ctx, conn)
        elif action_name == 'wipprs':
            await _wipprs(staff_login, action_value, chat_id, ctx, conn)
        elif action_name == 'startrek':
            await _startrek(staff_login, action_value, chat_id, ctx, conn)
        else:
            raise Exception(f'unsupported action_name: {action_name}')
