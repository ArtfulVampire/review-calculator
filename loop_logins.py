import logging

import staff
import storage


logger = logging.getLogger()


async def update_logins(ctx):
    async with ctx.pool.acquire() as conn:
        logger.info(f'update_logins start')
        pg_logins_data = await storage.get_all_staff_logins(conn)
        logger.info(f'staff_login -> telegram_login: {pg_logins_data}')

        staff_logins_data = await staff.get_telegram_logins(
            pg_logins_data.keys(), ctx,
        )
        logger.info(f'staff_logins_data: {staff_logins_data}')

        staff_logins_to_deregister: list = []

        for staff_login, telegram_login in pg_logins_data.items():
            if telegram_login not in staff_logins_data.get(staff_login, set()):
                staff_logins_to_deregister.append(staff_login)

        if staff_logins_to_deregister:
            logger.warning(
                'some staff_logins to deregister:'
                f' {staff_logins_to_deregister}',
            )
            await storage.delete_users_mappings(
                staff_logins_to_deregister, conn,
            )
