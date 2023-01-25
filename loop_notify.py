import datetime as dt
import logging

import calendarm
import github
import storage
import telegram


logger = logging.getLogger()


async def process_notify(ctx):
    async with ctx.pool.acquire() as conn:
        subjects_with_settings = await storage.get_reviewers_settings(conn)
        utcnow = dt.datetime.utcnow()
        current_hour = utcnow.hour + 3  # TODO timezone via settings

        github_logins = {
            login
            for login, settings in subjects_with_settings.items()
            if current_hour in settings['hours']
            and await calendarm.is_working_day(utcnow, login, ctx)
        }
        # github_logins = {'artfulvampire'}  # for test
        if github_logins:
            logger.info(f'users to notify {github_logins}')

        for github_login, settings in subjects_with_settings.items():
            if github_login not in github_logins:
                continue
            logger.debug(f'processing user {github_login}')

            # TODO reviews.show_requested

            prs = await github.get_requested_reviews(github_login, ctx)
            if not settings['wip']:
                prs = [pr for pr in prs if not pr.is_wip]

            if not prs:
                logger.debug(f'no prs to notify {github_login}')
            else:
                logger.info(
                    f'notify {github_login} on {len(prs)} prs: '
                    f'{[pr.get_short_slug() for pr in prs]}',
                )

            prs_abandoned = (
                (
                    await github.get_abandoned_prs(
                        github_login, dt.timedelta(days=14), ctx,  # config
                    )
                )
                if settings['my']
                else []
            )

            tg_login = await storage.get_telegram_login_pg(
                github_login, conn,
            )
            if not tg_login:
                logger.debug(f'tg_login not found, login = {github_login}')
                continue

            chat_id: str = await storage.get_chat_id(tg_login, conn)
            if not chat_id:
                logger.debug('chat_id not found')
                continue

            if not prs and not prs_abandoned:
                logger.debug('nothing to notify about')
                continue

            await telegram.send_message(
                await telegram.hourly_notification(prs, prs_abandoned, ctx),
                str(chat_id),
                ctx,
            )
