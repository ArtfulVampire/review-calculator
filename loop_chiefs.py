import logging

import staff
import storage

logger = logging.getLogger()


async def update_subordinated(ctx):
    async with ctx.pool.acquire() as conn:
        logger.info('start update_subordinated')
        subjects_with_settings = await storage.get_reviewers_settings(conn)

        for staff_login in subjects_with_settings.keys():
            subordinated_n = await staff.get_subordinated_nearest(
                staff_login, ctx,
            )
            if not subordinated_n:
                continue

            subordinated_a = await staff.get_subordinated_all(staff_login, ctx)
            logger.info(
                f'{staff_login} got {len(subordinated_n)} direct subordinates'
                f' and {len(subordinated_a)} total subordinates',
            )

            await storage.set_subordinated(
                staff_login, subordinated_n, subordinated_a, conn,
            )
