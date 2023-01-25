import datetime as dt
import logging
import typing as tp

import github
import storage
import telegram


logger = logging.getLogger()


async def _show(
        prs: tp.Collection[github.PullRequest],
        github_login: str,
        chat_id: str,
        show_to_close: bool,
        ctx,
) -> bool:
    settings = await storage.get_reviewer_settings(github_login, ctx.conn)
    if not settings:
        logger.warning(f'Empty settings for {github_login}, wipprs = ON')

    if settings and not settings['wip']:
        prs = [pr for pr in prs if not pr.is_wip]

    logger.info(f'notify {github_login} on {len(prs)} prs')

    prs_to_close = []
    if show_to_close:
        prs_to_close = await github.get_abandoned_prs(
            github_login, dt.timedelta(days=14), ctx,  # config
        )

    if not prs and not prs_to_close:
        logger.info(f'dont notify {github_login}')
        return False

    await telegram.send_message(
        await telegram.hourly_notification(prs, prs_to_close, ctx),
        chat_id,
        ctx,
    )
    return True


async def show_requested(
        github_login: str, chat_id: str, show_to_close: bool, ctx,
) -> bool:
    prs = await github.get_requested_reviews(github_login, ctx)

    return await _show(prs, github_login, chat_id, show_to_close, ctx)


async def get_current(github_login: str, chat_id: str, ctx) -> bool:
    now = dt.datetime.utcnow()
    prs = await github.get_reviewed_prs(
        github_login,
        now - dt.timedelta(days=10),  # TODO config
        now,
        False,
        ctx,
    )
    return await _show(prs, github_login, chat_id, False, ctx)
