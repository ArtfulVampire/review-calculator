import datetime as dt

import staff
import storage


async def update_gaps_info(ctx):
    async with ctx.pool.acquire() as conn:
        subjects_with_settings = await storage.get_reviewers_settings(conn)

        for staff_login in subjects_with_settings.keys():
            today = dt.date.today()
            gaps = await staff.get_absent_time(
                staff_login, today, today + dt.timedelta(days=14), ctx,
            )
            await storage.set_gaps(staff_login, gaps, conn)
