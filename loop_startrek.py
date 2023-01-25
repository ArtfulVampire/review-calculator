import datetime as dt
import logging

import calendarm
import staff
import storage
import telegram


logger = logging.getLogger()


async def notify_startrek(ctx):
    logger.info('notify_startrek started')
    async with ctx.pool.acquire() as conn:
        subjects_with_settings = await storage.get_reviewers_settings(conn)
        utcnow = dt.datetime.utcnow()

        staff_logins = {
            login
            for login, settings in subjects_with_settings.items()
            if settings['startrek']
            and await calendarm.is_working_day(utcnow, login, ctx)
        }
        logger.info(f'try notify {len(staff_logins)} about startrek')
        # staff_logins = {'artfulvampire'}  # test

        counter = 0
        pp_counter = 0
        for staff_login in subjects_with_settings.keys():
            if staff_login not in staff_logins:
                # pass
                continue

            logger.debug(f'startrack processing user {staff_login}')

            tg_login: str = await storage.get_telegram_login_pg(
                staff_login, conn,
            )
            if not tg_login:
                logger.warning(f'tg_login not found for {staff_login}')
                continue

            chat_id: str = await storage.get_chat_id(tg_login, conn)
            if not chat_id:
                logger.warning(f'chat_id not found for {staff_login}')
                continue

            # really notify
            is_partner_products = await staff.is_partner_product(
                staff_login, conn,
            )
            counter += 1
            pp_counter += int(is_partner_products)

            await telegram.send_message(
                await telegram.startrack_message(
                    staff_login, is_partner_products, ctx,
                ),
                chat_id,
                ctx,
            )

        logger.info(
            f'actually notified {counter} users about startrek'
            f', {pp_counter} from partner products (about tags)',
        )
